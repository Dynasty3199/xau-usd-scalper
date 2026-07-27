"""
Generates a synthetic minute-level XAUUSD OHLCV CSV so the pipeline can be
test-run locally without a data subscription.

This is NOT real market data - it's a seeded random walk. Swap it out for
real history from Dukascopy, HistData, Databento, or Polygon.io before
trusting any backtest result from this project.
"""

from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(7)


def generate(
    start: str = "2026-06-01",
    days: int = 30,
    out_path: str = "data/raw/XAUUSD_sample.csv",
) -> None:
    idx = pd.date_range(start=start, periods=days * 24 * 60, freq="1min", tz="UTC")

    # Crude 24/5 mask matching clean_ohlcv's weekend-gap logic.
    weekday, hour = idx.dayofweek, idx.hour
    keep = ~((weekday == 5) | ((weekday == 6) & (hour < 22)) | ((weekday == 4) & (hour >= 22)))
    idx = idx[keep]

    n = len(idx)
    vol = 0.35  # ~ typical 1-min gold noise, in price points
    returns = RNG.normal(0.0, vol, n)
    # A few synthetic "volatility spike" windows so the ATR-spike veto has
    # something real to trigger on when you run the backtest.
    spike_starts = RNG.choice(np.arange(200, n - 200), size=max(1, n // 8000), replace=False)
    for s in spike_starts:
        returns[s : s + 30] *= RNG.uniform(6, 10)

    close = 2400 + np.cumsum(returns)
    high = close + RNG.uniform(0.05, 0.5, n)
    low = close - RNG.uniform(0.05, 0.5, n)
    open_ = close - returns
    volume = RNG.integers(50, 500, n)

    df = pd.DataFrame(
        {"timestamp": idx, "open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )

    out_path = Path(out_path) # type: ignore
    out_path.parent.mkdir(parents=True, exist_ok=True) # type: ignore
    df.to_csv(out_path, index=False)
    print(f"Wrote {n:,} synthetic bars to {out_path}")


if __name__ == "__main__":
    generate()
     