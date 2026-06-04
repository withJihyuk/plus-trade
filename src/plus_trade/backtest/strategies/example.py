"""Example strategy used only to exercise the backtest engine."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MovingAverageCrossStrategy:
    fast_window: int = 5
    slow_window: int = 20

    def target_weights(self, bars: pd.DataFrame) -> pd.Series:
        close = bars.sort_values("timestamp")["close"].astype(float)
        fast = close.rolling(self.fast_window, min_periods=1).mean()
        slow = close.rolling(self.slow_window, min_periods=1).mean()
        weights = (fast > slow).astype(float)
        timestamps = pd.to_datetime(bars.sort_values("timestamp")["timestamp"], utc=True)
        return pd.Series(weights.to_numpy(), index=timestamps, name="target_weight")
