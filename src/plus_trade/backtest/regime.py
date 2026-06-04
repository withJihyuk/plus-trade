"""Market regime classification."""

from __future__ import annotations

from enum import StrEnum

import pandas as pd


class RegimeLabel(StrEnum):
    UPTREND_LOW_VOL = "uptrend_low_vol"
    UPTREND_HIGH_VOL = "uptrend_high_vol"
    DOWNTREND_LOW_VOL = "downtrend_low_vol"
    DOWNTREND_HIGH_VOL = "downtrend_high_vol"
    SIDEWAYS_LOW_VOL = "sideways_low_vol"
    SIDEWAYS_HIGH_VOL = "sideways_high_vol"


def classify_trend_vol_regime(
    benchmark_bars: pd.DataFrame,
    *,
    trend_window: int = 20,
    volatility_window: int = 20,
) -> pd.Series:
    bars = benchmark_bars.sort_values("timestamp").copy()
    close = bars["close"].astype(float)
    returns = close.pct_change()
    moving_average = close.rolling(trend_window, min_periods=1).mean()
    volatility = returns.rolling(volatility_window, min_periods=2).std()
    volatility_threshold = volatility.expanding(min_periods=2).median()

    labels: list[str] = []
    for price, ma, vol, threshold in zip(close, moving_average, volatility, volatility_threshold, strict=False):
        if price > ma * 1.005:
            trend = "uptrend"
        elif price < ma * 0.995:
            trend = "downtrend"
        else:
            trend = "sideways"
        vol_label = "high_vol" if pd.notna(vol) and pd.notna(threshold) and vol > threshold else "low_vol"
        labels.append(f"{trend}_{vol_label}")

    return pd.Series(labels, index=pd.to_datetime(bars["timestamp"], utc=True), name="regime")
