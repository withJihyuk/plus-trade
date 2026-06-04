from datetime import UTC

import pandas as pd

from plus_trade.backtest.fills import simulate_target_weight_fills


def test_target_weight_uses_next_bar_open_without_lookahead() -> None:
    bars = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-02 14:30", periods=3, freq="min", tz=UTC),
            "symbol": ["AAPL"] * 3,
            "open": [100, 110, 120],
            "high": [100, 110, 120],
            "low": [100, 110, 120],
            "close": [100, 999, 120],
            "volume": [1_000, 1_000, 1_000],
        }
    )
    target_weights = pd.Series([1.0, 1.0, 1.0], index=bars["timestamp"])

    fills = simulate_target_weight_fills(
        bars,
        target_weights,
        initial_capital=1_000,
        volume_participation_cap=1.0,
        slippage_bps=0,
    )

    assert len(fills) == 1
    assert fills.iloc[0]["timestamp"] == bars.iloc[1]["timestamp"]
    assert fills.iloc[0]["price"] == 110


def test_volume_participation_cap_limits_filled_quantity() -> None:
    bars = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-02 14:30", periods=2, freq="min", tz=UTC),
            "symbol": ["AAPL"] * 2,
            "open": [100, 100],
            "high": [100, 100],
            "low": [100, 100],
            "close": [100, 100],
            "volume": [100, 10],
        }
    )
    target_weights = pd.Series([1.0, 1.0], index=bars["timestamp"])

    fills = simulate_target_weight_fills(
        bars,
        target_weights,
        initial_capital=10_000,
        volume_participation_cap=0.2,
        slippage_bps=0,
    )

    assert fills.iloc[0]["requested_qty"] == 100
    assert fills.iloc[0]["filled_qty"] == 2
