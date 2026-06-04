import pandas as pd

from plus_trade.backtest.metrics import calculate_metrics


def test_metrics_calculate_total_return_and_max_drawdown() -> None:
    equity = pd.Series([100, 120, 90, 150], dtype=float)

    metrics = calculate_metrics(equity, periods_per_year=252)

    assert metrics.total_return == 0.5
    assert round(metrics.max_drawdown, 4) == -0.25
    assert metrics.calmar > 0


def test_metrics_handle_flat_equity_curve() -> None:
    equity = pd.Series([100, 100, 100], dtype=float)

    metrics = calculate_metrics(equity, periods_per_year=252)

    assert metrics.total_return == 0
    assert metrics.volatility == 0
    assert metrics.sharpe == 0
    assert metrics.sortino == 0
    assert metrics.max_drawdown == 0
