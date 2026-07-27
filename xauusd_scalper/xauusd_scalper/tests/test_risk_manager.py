"""
Sanity tests for the Risk Manager circuit breaker.
Run directly: `python tests/test_risk_manager.py`
(function names are also pytest-discoverable if you have pytest installed)
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.risk_manager import RiskManager, RiskConfig  # noqa: E402


def test_daily_drawdown_halts_new_trades():
    rm = RiskManager(RiskConfig(starting_equity=10_000, max_daily_drawdown_pct=2.0))
    ts = pd.Timestamp("2026-06-01 10:00", tz="UTC")

    rm.approve_signal(ts, signal=1, atr=1.0, atr_avg=1.0)
    rm.update_equity(-250)  # -2.5% > 2% max daily drawdown

    decision = rm.approve_signal(ts, signal=1, atr=1.0, atr_avg=1.0)
    assert not decision["approved"], "Risk manager should veto trades after breaching max daily drawdown"
    assert decision["reason"] == "daily_drawdown_halt"
    print("PASS: daily drawdown halt")


def test_atr_spike_blocks_trade():
    rm = RiskManager(RiskConfig(atr_spike_mult=3.0))
    ts = pd.Timestamp("2026-06-01 10:00", tz="UTC")

    decision = rm.approve_signal(ts, signal=1, atr=10.0, atr_avg=1.0)  # 10x normal ATR
    assert not decision["approved"], "Risk manager should veto trades during an ATR spike"
    assert decision["reason"] == "volatility_spike"
    print("PASS: ATR spike veto")


def test_position_sizing_respects_risk_per_trade():
    rm = RiskManager(RiskConfig(starting_equity=10_000, risk_per_trade_pct=1.0, stop_loss_atr_mult=2.0))
    size = rm.position_size(entry_price=2400.0, atr=5.0)
    # risk_amount = 100 (1% of 10k); stop_distance = 10 (2 * atr 5); size = 10
    assert abs(size - 10.0) < 1e-6, f"Expected size 10.0, got {size}"
    print("PASS: position sizing")


def test_new_day_resets_halt():
    rm = RiskManager(RiskConfig(starting_equity=10_000, max_daily_drawdown_pct=2.0))
    day1 = pd.Timestamp("2026-06-01 10:00", tz="UTC")
    day2 = pd.Timestamp("2026-06-02 10:00", tz="UTC")

    rm.approve_signal(day1, signal=1, atr=1.0, atr_avg=1.0)
    rm.update_equity(-250)
    rm.approve_signal(day1, signal=1, atr=1.0, atr_avg=1.0)  # halts for the rest of day1

    decision = rm.approve_signal(day2, signal=1, atr=1.0, atr_avg=1.0)
    assert decision["approved"], "A new trading day should reset the halt"
    print("PASS: new day resets halt")


if __name__ == "__main__":
    test_daily_drawdown_halts_new_trades()
    test_atr_spike_blocks_trade()
    test_position_sizing_respects_risk_per_trade()
    test_new_day_resets_halt()
    print("\nAll risk manager sanity tests passed.")
