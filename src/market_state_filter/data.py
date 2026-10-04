"""Synthetic OHLCV and validated local CSV input. No exchange/private access."""
from pathlib import Path
import numpy as np
import pandas as pd

REQUIRED = ["timestamp", "open", "high", "low", "close", "volume"]

def validate_bars(frame):
    missing = set(REQUIRED) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    frame = frame[REQUIRED].copy()
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True, errors="raise")
    if frame.timestamp.isna().any() or frame.timestamp.duplicated().any() or not frame.timestamp.is_monotonic_increasing:
        raise ValueError("Timestamps must be strictly increasing and unique")
    if len(frame) > 2 and frame.timestamp.diff().dropna().nunique() != 1:
        raise ValueError("Bar intervals must be uniform; repair gaps before research")
    frame[REQUIRED[1:]] = frame[REQUIRED[1:]].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(frame[REQUIRED[1:]].to_numpy()).all():
        raise ValueError("Nonfinite OHLCV")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any() or (frame.volume < 0).any():
        raise ValueError("Prices must be positive and volume nonnegative")
    if ((frame.high < frame[["open", "close", "low"]].max(axis=1)) |
        (frame.low > frame[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC bounds")
    return frame.reset_index(drop=True)

def synthetic_bars(count=1200, seed=7):
    if count < 100:
        raise ValueError("At least 100 bars required")
    rng = np.random.default_rng(seed)
    x = np.arange(count)
    close = 100 + .008*x + 4*np.sin(x/22) + 2*np.sin(x/73) + np.cumsum(rng.normal(0, .28, count))
    close = np.maximum(close, 10)
    opening = np.r_[close[0], close[:-1]] + rng.normal(0, .12, count)
    high = np.maximum(opening, close) + rng.uniform(.15, .9, count)
    low = np.minimum(opening, close) - rng.uniform(.15, .9, count)
    return validate_bars(pd.DataFrame({"timestamp": pd.date_range("2025-01-01", periods=count, freq="h", tz="UTC"),
        "open": opening, "high": high, "low": low, "close": close, "volume": rng.uniform(100, 1000, count)}))

def read_csv(path):
    return validate_bars(pd.read_csv(Path(path)))

def atr_series(bars, window=14):
    prev = bars.close.shift(1)
    tr = pd.concat([bars.high-bars.low, (bars.high-prev).abs(), (bars.low-prev).abs()], axis=1).max(axis=1)
    return tr.rolling(window, min_periods=1).mean().to_numpy()
