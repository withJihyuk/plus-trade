from datetime import UTC

import pandas as pd

from plus_trade.backtest.models import Timeframe
from plus_trade.backtest.resample import resample_bars


def test_resample_1m_bars_to_5m_ohlcv() -> None:
    timestamps = pd.date_range("2026-01-02 14:30", periods=5, freq="min", tz=UTC)
    bars = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["AAPL"] * 5,
            "open": [100, 101, 102, 103, 104],
            "high": [101, 103, 104, 106, 105],
            "low": [99, 100, 101, 102, 103],
            "close": [100.5, 102.5, 103.5, 104.5, 104.0],
            "volume": [10, 20, 30, 40, 50],
        }
    )

    result = resample_bars(bars, Timeframe.FIVE_MINUTES)

    assert len(result) == 1
    row = result.iloc[0]
    assert row["timestamp"] == timestamps[0]
    assert row["symbol"] == "AAPL"
    assert row["open"] == 100
    assert row["high"] == 106
    assert row["low"] == 99
    assert row["close"] == 104.0
    assert row["volume"] == 150


def test_resample_preserves_symbols_separately() -> None:
    timestamps = pd.date_range("2026-01-02 14:30", periods=2, freq="min", tz=UTC)
    bars = pd.DataFrame(
        {
            "timestamp": list(timestamps) * 2,
            "symbol": ["AAPL", "AAPL", "MSFT", "MSFT"],
            "open": [100, 101, 200, 201],
            "high": [102, 103, 202, 203],
            "low": [99, 100, 199, 200],
            "close": [101, 102, 201, 202],
            "volume": [10, 20, 30, 40],
        }
    )

    result = resample_bars(bars, Timeframe.FIVE_MINUTES)

    assert list(result["symbol"]) == ["AAPL", "MSFT"]
    assert list(result["volume"]) == [30, 70]
