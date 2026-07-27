"""
Data Ingestion
--------------
Loads raw tick or minute-level CSV data and normalizes it into a clean,
UTC-indexed OHLCV pandas DataFrame. Handles timezone parsing and the
weekend gaps that FX/gold markets have (closed roughly Fri 22:00 UTC ->
Sun 22:00 UTC, broker-dependent).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import pandas as pd

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


def load_raw_csv(filepath: PathLike, timestamp_col: str = "timestamp") -> pd.DataFrame:
    """
    Load a raw CSV into a DataFrame with a parsed, UTC-aware datetime index.

    Accepts columns that map to timestamp/open/high/low/close/volume
    (case-insensitive), or tick data with bid/ask columns.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(
            f"No data file found at {filepath}. Run scripts/generate_sample_data.py "
            "for a synthetic test file, or point this at real history from "
            "Dukascopy / HistData / Databento / Polygon.io."
        )

    df = pd.read_csv(filepath)
    df.columns = [c.strip().lower() for c in df.columns]

    if timestamp_col not in df.columns:
        for alt in ("time", "datetime", "date"):
            if alt in df.columns:
                timestamp_col = alt
                break
        else:
            raise ValueError(f"Could not find a timestamp column in {filepath.name}")

    df[timestamp_col] = pd.to_datetime(df[timestamp_col], utc=True, errors="coerce")
    df = df.dropna(subset=[timestamp_col])
    df = df.set_index(timestamp_col).sort_index()
    df.index.name = "timestamp"
    return df


def ticks_to_ohlcv(tick_df: pd.DataFrame, bar_size: str = "1min") -> pd.DataFrame:
    """Resample raw tick data (bid/ask or a single price column) into OHLCV bars."""
    df = tick_df.copy()

    if "mid" in df.columns:
        price_col = "mid"
    elif {"bid", "ask"}.issubset(df.columns):
        df["mid"] = (df["bid"] + df["ask"]) / 2.0
        price_col = "mid"
    else:
        raise ValueError("Tick data needs a 'mid' price column, or both 'bid' and 'ask'.")

    ohlc = df[price_col].resample(bar_size).ohlc()
    if "volume" in df.columns:
        vol = df["volume"].resample(bar_size).sum()
    else:
        vol = df[price_col].resample(bar_size).count().rename("volume")

    bars = ohlc.join(vol)
    return bars.dropna(subset=["open", "high", "low", "close"])


def clean_ohlcv(df: pd.DataFrame, drop_weekend_gap: bool = True) -> pd.DataFrame:
    """
    Normalize an OHLCV DataFrame: enforce column names, drop duplicate
    timestamps, patch tiny feed gaps, and drop the weekend gap rather than
    forward-filling a flat/fake price through it.
    """
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required OHLC columns: {missing}")

    if "volume" not in df.columns:
        df["volume"] = 0.0

    df = df[~df.index.duplicated(keep="last")].sort_index()

    if drop_weekend_gap:
        weekday, hour = df.index.dayofweek, df.index.hour
        is_weekend_gap = (
            (weekday == 5)                       # Saturday: closed all day
            | ((weekday == 6) & (hour < 22))      # Sunday before reopen
            | ((weekday == 4) & (hour >= 22))     # Friday after close
        )
        df = df.loc[~is_weekend_gap]

    # Patch isolated missing bars (brief feed dropouts) but never fabricate
    # more than a few consecutive bars of flat price.
    ohlc_cols = ["open", "high", "low", "close"]
    df[ohlc_cols] = df[ohlc_cols].ffill(limit=3)
    df = df.dropna(subset=ohlc_cols)

    return df


def load_and_prepare(
    raw_path: PathLike,
    processed_path: PathLike | None = None,
    is_tick_data: bool = False,
    bar_size: str = "1min",
) -> pd.DataFrame:
    """Full pipeline: load raw file -> (optional) resample ticks -> clean -> save."""
    raw = load_raw_csv(raw_path)

    if is_tick_data:
        raw = ticks_to_ohlcv(raw, bar_size=bar_size)

    clean = clean_ohlcv(raw)

    if processed_path is not None:
        processed_path = Path(processed_path)
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        clean.to_csv(processed_path)
        logger.info("Saved %d clean bars to %s", len(clean), processed_path)

    return clean
