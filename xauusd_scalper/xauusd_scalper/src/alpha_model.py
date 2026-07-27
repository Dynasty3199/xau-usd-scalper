"""
Alpha Model
-----------
Signal generator for the gold scalping strategy: a 9/21 EMA crossover,
confirmed by an ATR volatility filter. Tries pandas-ta first (matching the
stated stack) and transparently falls back to a manual pandas/numpy
implementation if pandas-ta isn't installed or fails to import (it has a
known incompatibility with NumPy 2.x as of this writing).
"""

from __future__ import annotations

import importlib
from typing import Any

import numpy as np
import pandas as pd

try:
    ta: Any = importlib.import_module("pandas_ta")
    _HAS_PANDAS_TA = True
except Exception:  # pragma: no cover - environment dependent
    ta = None
    _HAS_PANDAS_TA = False


def _ema(series: pd.Series, length: int) -> pd.Series:
    if _HAS_PANDAS_TA:
        result = ta.ema(series, length=length)
        if result is not None:
            return result
    return series.ewm(span=length, adjust=False).mean()


def _atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    if _HAS_PANDAS_TA:
        result = ta.atr(df["high"], df["low"], df["close"], length=length)
        if result is not None:
            return result
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


def add_indicators(df: pd.DataFrame, ema_fast: int = 9, ema_slow: int = 21, atr_period: int = 14) -> pd.DataFrame:
    """Attach ema_fast, ema_slow, atr, and atr_avg columns to an OHLCV DataFrame."""
    out = df.copy()
    out["ema_fast"] = _ema(out["close"], ema_fast)
    out["ema_slow"] = _ema(out["close"], ema_slow)
    out["atr"] = _atr(out, atr_period)
    out["atr_avg"] = out["atr"].rolling(100, min_periods=20).mean()
    return out


def generate_signals(
    df: pd.DataFrame,
    ema_fast: int = 9,
    ema_slow: int = 21,
    atr_period: int = 14,
    atr_spike_mult: float = 3.0,
    atr_quiet_mult: float = 0.3,
    warmup_bars: int = 50,
) -> pd.DataFrame:
    """
    Generate long/short/flat signals from EMA crossovers, filtered by ATR.

    signal: 1 = long entry, -1 = short entry, 0 = no signal.
    A crossover is suppressed (signal forced to 0) when ATR shows either an
    extreme spike (the Risk Manager should be suspicious of it) or an
    abnormally quiet regime (low-quality noise on a scalping timeframe).
    `warmup_bars` also suppresses signals until the EMAs/ATR average have
    had time to settle, avoiding false crossovers from indicator seeding.
    """
    out = add_indicators(df, ema_fast, ema_slow, atr_period)

    prev_fast = out["ema_fast"].shift(1)
    prev_slow = out["ema_slow"].shift(1)

    cross_up = (prev_fast <= prev_slow) & (out["ema_fast"] > out["ema_slow"])
    cross_down = (prev_fast >= prev_slow) & (out["ema_fast"] < out["ema_slow"])

    normal_volatility = (out["atr"] < out["atr_avg"] * atr_spike_mult) & (
        out["atr"] > out["atr_avg"] * atr_quiet_mult
    )

    out["signal"] = 0
    out.loc[cross_up & normal_volatility, "signal"] = 1
    out.loc[cross_down & normal_volatility, "signal"] = -1

    if warmup_bars > 0 and len(out) > 0:
        out.iloc[: min(warmup_bars, len(out)), out.columns.get_loc("signal")] = 0 # type: ignore

    out["volatility_flag"] = np.where(
        out["atr"] >= out["atr_avg"] * atr_spike_mult,
        "spike",
        np.where(out["atr"] <= out["atr_avg"] * atr_quiet_mult, "quiet", "normal"),
    )

    return out
