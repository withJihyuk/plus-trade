import pandas as pd

from plus_trade.backtest.walk_forward import generate_walk_forward_splits


def test_walk_forward_splits_preserve_time_order_and_do_not_overlap() -> None:
    sessions = pd.date_range("2026-01-01", periods=10, freq="D")

    splits = generate_walk_forward_splits(sessions, train_days=4, test_days=2)

    assert len(splits) == 3
    first = splits[0]
    assert first.train_start == sessions[0]
    assert first.train_end == sessions[3]
    assert first.test_start == sessions[4]
    assert first.test_end == sessions[5]
    assert first.train_end < first.test_start
