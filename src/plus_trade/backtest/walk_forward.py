"""Walk-forward split generation."""

from __future__ import annotations

import pandas as pd

from plus_trade.backtest.models import WalkForwardSplit


def generate_walk_forward_splits(
    sessions: pd.DatetimeIndex,
    *,
    train_days: int,
    test_days: int,
) -> list[WalkForwardSplit]:
    ordered = pd.DatetimeIndex(sessions).sort_values().unique()
    splits: list[WalkForwardSplit] = []
    start = 0

    while start + train_days + test_days <= len(ordered):
        train_start_idx = start
        train_end_idx = start + train_days - 1
        test_start_idx = train_end_idx + 1
        test_end_idx = test_start_idx + test_days - 1
        splits.append(
            WalkForwardSplit(
                train_start=ordered[train_start_idx],
                train_end=ordered[train_end_idx],
                test_start=ordered[test_start_idx],
                test_end=ordered[test_end_idx],
            )
        )
        start += test_days

    return splits
