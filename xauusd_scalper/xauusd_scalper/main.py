"""
Event loop: Data Ingestion -> Alpha Model -> Risk Manager -> Execution Router.
Runs a bar-by-bar backtest over historical OHLCV data and prints a summary.
"""

from __future__ import annotations

import logging

import pandas as pd

import settings
from src.data_ingestion import load_and_prepare
from src.alpha_model import generate_signals
from src.risk_manager import RiskManager
from src.execution_router import SimulatedBroker, Order

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("main")


def run_backtest() -> pd.DataFrame:
    df = load_and_prepare(settings.RAW_DATA_PATH, settings.PROCESSED_DATA_PATH)
    df = generate_signals(
        df,
        ema_fast=settings.EMA_FAST,
        ema_slow=settings.EMA_SLOW,
        atr_period=settings.ATR_PERIOD,
        atr_spike_mult=settings.ATR_SPIKE_MULT,
        atr_quiet_mult=settings.ATR_QUIET_MULT,
        warmup_bars=settings.WARMUP_BARS,
    )

    risk = RiskManager(settings.RISK_CONFIG)
    broker = SimulatedBroker(slippage_points=settings.SLIPPAGE_POINTS)

    position = 0.0
    entry_price = None
    equity_curve = []
    veto_counts: dict[str, int] = {}

    for ts, row in df.iterrows():
        price = row["close"]

        unrealized = (price - entry_price) * position if position != 0 else 0.0
        equity_curve.append({"timestamp": ts, "equity": risk.equity + unrealized})

        decision = risk.approve_signal(ts, row["signal"], row["atr"], row["atr_avg"])
        if not decision["approved"]:
            veto_counts[decision["reason"]] = veto_counts.get(decision["reason"], 0) + 1
            continue

        # Close an opposing open position before considering a new one.
        if position != 0 and ((row["signal"] == 1 and position < 0) or (row["signal"] == -1 and position > 0)):
            fill = broker.execute(Order(ts, "buy" if position < 0 else "sell", abs(position)), price)
            risk.update_equity((fill.price - entry_price) * position) # type: ignore
            position, entry_price = 0.0, None

        if position == 0:
            size = risk.position_size(price, row["atr"])
            if not size or size <= 0:
                continue
            side = "buy" if row["signal"] == 1 else "sell"
            fill = broker.execute(Order(ts, side, size), price)
            position = size if side == "buy" else -size
            entry_price = fill.price

    equity_df = pd.DataFrame(equity_curve).set_index("timestamp")
    _print_summary(equity_df, broker, veto_counts)
    return equity_df


def _print_summary(equity_df: pd.DataFrame, broker: SimulatedBroker, veto_counts: dict) -> None:
    start, end = equity_df["equity"].iloc[0], equity_df["equity"].iloc[-1]
    running_max = equity_df["equity"].cummax()
    max_dd = ((running_max - equity_df["equity"]) / running_max).max() * 100

    print("\n===== Backtest Summary =====")
    print(f"Starting equity : {start:,.2f}")
    print(f"Ending equity   : {end:,.2f}")
    print(f"Return          : {(end / start - 1) * 100:,.2f}%")
    print(f"Max drawdown    : {max_dd:,.2f}%")
    print(f"Total fills     : {len(broker.fills)}")
    print(f"Signals vetoed  : {veto_counts}")


if __name__ == "__main__":
    run_backtest()
