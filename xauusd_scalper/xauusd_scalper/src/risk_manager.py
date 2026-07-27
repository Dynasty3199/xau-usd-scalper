"""
Risk Manager
------------
The circuit breaker. Holds veto power over every signal produced by the
Alpha Model. Nothing reaches the Execution Router unless it clears:
  1. Max daily drawdown check (halts new trades for the rest of the day)
  2. Volatility sanity check (blocks entries during an ATR spike)
  3. Position sizing tied to a fixed % of equity risked per trade

This module encodes the "no mistake-free algorithm, only strict and
unyielding risk parameters" philosophy - it never tries to be smart about
overriding its own limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    starting_equity: float = 100
    risk_per_trade_pct: float = 1.0        # % of equity risked per trade
    max_daily_drawdown_pct: float = 2.0    # % of equity; halts trading for the day if breached
    atr_spike_mult: float = 3.0            # veto trades if ATR >= this multiple of its rolling average
    stop_loss_atr_mult: float = 1.5        # stop distance used for position sizing
    max_trades_per_day: int = 20


class RiskManager:
    """Stateful circuit breaker: tracks equity, daily drawdown, and trade count."""

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()
        self.equity = self.config.starting_equity
        self._day: date | None = None
        self._day_start_equity = self.equity
        self._trades_today = 0
        self.halted_today = False

    def _roll_day_if_needed(self, timestamp) -> None:
        current_day = timestamp.date()
        if self._day != current_day:
            self._day = current_day
            self._day_start_equity = self.equity
            self._trades_today = 0
            self.halted_today = False
            logger.info("New trading day %s | equity=%.2f", current_day, self.equity)

    def _daily_drawdown_pct(self) -> float:
        if self._day_start_equity <= 0:
            return 0.0
        return (self._day_start_equity - self.equity) / self._day_start_equity * 100.0

    def position_size(self, entry_price: float, atr: float) -> float:
        """
        Size a position so a stop at `stop_loss_atr_mult * ATR` away loses
        exactly `risk_per_trade_pct` of current equity. Returns units (e.g.
        troy ounces of gold).
        """
        if atr is None or atr != atr or atr <= 0:  # NaN-safe check
            return 0.0
        stop_distance = atr * self.config.stop_loss_atr_mult
        if stop_distance <= 0:
            return 0.0
        risk_amount = self.equity * (self.config.risk_per_trade_pct / 100.0)
        return round(risk_amount / stop_distance, 4)

    def approve_signal(self, timestamp, signal: int, atr: float, atr_avg: float) -> dict:
        """
        Veto or approve a raw signal from the Alpha Model. Returns a dict
        describing the decision - a veto is a normal, expected outcome,
        never an error/exception.
        """
        self._roll_day_if_needed(timestamp)

        if not signal:
            return {"approved": False, "reason": "no_signal"}

        if self.halted_today:
            return {"approved": False, "reason": "daily_drawdown_halt"}

        if self._daily_drawdown_pct() >= self.config.max_daily_drawdown_pct:
            self.halted_today = True
            logger.warning(
                "Max daily drawdown breached at %s - halting new trades for the day.", timestamp
            )
            return {"approved": False, "reason": "daily_drawdown_halt"}

        if atr_avg and atr_avg == atr_avg and atr >= atr_avg * self.config.atr_spike_mult:
            return {"approved": False, "reason": "volatility_spike"}

        if self._trades_today >= self.config.max_trades_per_day:
            return {"approved": False, "reason": "max_trades_reached"}

        self._trades_today += 1
        return {"approved": True, "reason": "ok"}

    def update_equity(self, pnl: float) -> None:
        self.equity += pnl
