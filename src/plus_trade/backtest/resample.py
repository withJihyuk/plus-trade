"""OHLCV bar resampling."""

from __future__ import annotations

import pandas as pd

from plus_trade.backtest.models import Timeframe


REQUIRED_BAR_COLUMNS = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]


def normalize_bars(bars: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_BAR_COLUMNS if column not in bars.columns]
    if missing:
        raise ValueError(f"bars missing columns: {', '.join(missing)}")

    normalized = bars.loc[:, REQUIRED_BAR_COLUMNS].copy()
    normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True)
    return normalized.sort_values(["symbol", "timestamp"]).reset_index(drop=True)


def resample_bars(bars: pd.DataFrame, timeframe: Timeframe) -> pd.DataFrame:
    normalized = normalize_bars(bars)
    if timeframe is Timeframe.ONE_MINUTE:
        return normalized

    frames: list[pd.DataFrame] = []
    for symbol, symbol_bars in normalized.groupby("symbol", sort=True):
        indexed = symbol_bars.set_index("timestamp")
        offset = "30min" if timeframe is Timeframe.ONE_HOUR else None
        resampled = (
            indexed.resample(timeframe.pandas_rule, label="left", closed="left", offset=offset)
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna(subset=["open", "high", "low", "close"])
        )
        resampled["symbol"] = symbol
        frames.append(resampled.reset_index())

    if not frames:
        return normalized.iloc[0:0]

    return pd.concat(frames, ignore_index=True).loc[:, REQUIRED_BAR_COLUMNS]
