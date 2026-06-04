"""Performance metrics."""

from __future__ import annotations

import math

import pandas as pd

from plus_trade.backtest.models import PerformanceMetrics


def calculate_metrics(equity_curve: pd.Series, *, periods_per_year: int) -> PerformanceMetrics:
    equity = equity_curve.astype(float).dropna()
    if len(equity) < 2:
        return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0)

    start = float(equity.iloc[0])
    end = float(equity.iloc[-1])
    total_return = (end / start) - 1 if start else 0

    returns = equity.pct_change().dropna()
    years = max((len(equity) - 1) / periods_per_year, 1 / periods_per_year)
    cagr = (end / start) ** (1 / years) - 1 if start and end > 0 else 0

    volatility = float(returns.std(ddof=0) * math.sqrt(periods_per_year)) if not returns.empty else 0
    sharpe = float((returns.mean() / returns.std(ddof=0)) * math.sqrt(periods_per_year)) if returns.std(ddof=0) else 0

    downside = returns[returns < 0]
    sortino = (
        float((returns.mean() / downside.std(ddof=0)) * math.sqrt(periods_per_year))
        if not downside.empty and downside.std(ddof=0)
        else 0
    )

    running_max = equity.cummax()
    drawdowns = (equity / running_max) - 1
    max_drawdown = float(drawdowns.min()) if not drawdowns.empty else 0
    calmar = float(cagr / abs(max_drawdown)) if max_drawdown else 0

    return PerformanceMetrics(
        total_return=float(total_return),
        cagr=float(cagr),
        volatility=volatility,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=max_drawdown,
        calmar=calmar,
    )
