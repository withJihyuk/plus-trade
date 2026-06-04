"""Vector backtest engine."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from plus_trade.backtest.data import BarRepository, load_backtest_config, load_universe_config
from plus_trade.backtest.fills import PortfolioSimulation, simulate_target_weight_portfolio
from plus_trade.backtest.metrics import calculate_metrics
from plus_trade.backtest.models import BacktestRunConfig, PerformanceMetrics, Timeframe
from plus_trade.backtest.regime import classify_trend_vol_regime
from plus_trade.backtest.resample import resample_bars
from plus_trade.backtest.walk_forward import generate_walk_forward_splits


class Strategy(Protocol):
    def target_weights(self, bars: pd.DataFrame) -> pd.Series: ...


@dataclass(frozen=True)
class SymbolBacktestResult:
    symbol: str
    metrics: PerformanceMetrics
    simulation: PortfolioSimulation


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestRunConfig
    symbols: list[SymbolBacktestResult]
    oos_metrics: PerformanceMetrics | None
    regime_metrics: dict[str, PerformanceMetrics]


def load_strategy(config: BacktestRunConfig) -> Strategy:
    module = importlib.import_module(config.strategy.module)
    strategy_type = getattr(module, config.strategy.name)
    return strategy_type(**config.strategy.params)


def periods_per_year(timeframe: Timeframe) -> int:
    trading_days = 252
    minutes_per_day = 390
    if timeframe is Timeframe.ONE_MINUTE:
        return trading_days * minutes_per_day
    if timeframe is Timeframe.FIVE_MINUTES:
        return trading_days * (minutes_per_day // 5)
    return trading_days * (minutes_per_day // 15)


def run_backtest(config_path, repository: BarRepository | None = None) -> BacktestResult:
    config = load_backtest_config(config_path)
    universe = load_universe_config(config.universe)
    repo = repository or BarRepository()
    strategy = load_strategy(config)
    symbol_results: list[SymbolBacktestResult] = []

    for symbol in universe.symbols:
        bars = repo.read_bars(symbol, start=config.start, end=config.end, timeframe=Timeframe.ONE_MINUTE)
        run_bars = resample_bars(bars, config.timeframe)
        target_weights = strategy.target_weights(run_bars)
        simulation = simulate_target_weight_portfolio(
            run_bars,
            target_weights,
            initial_capital=config.initial_capital,
            fee_bps=config.costs.fee_bps,
            fx_spread_bps=config.costs.fx_spread_bps,
            slippage_bps=config.costs.slippage_bps,
            volume_participation_cap=config.costs.volume_participation_cap,
        )
        metrics = calculate_metrics(simulation.equity_curve, periods_per_year=periods_per_year(config.timeframe))
        symbol_results.append(SymbolBacktestResult(symbol=symbol, metrics=metrics, simulation=simulation))

    oos_metrics = _calculate_oos_metrics(config, symbol_results)
    regime_metrics = _calculate_regime_metrics(config, universe.benchmarks, repo, symbol_results)
    return BacktestResult(
        config=config,
        symbols=symbol_results,
        oos_metrics=oos_metrics,
        regime_metrics=regime_metrics,
    )


def _calculate_oos_metrics(
    config: BacktestRunConfig,
    symbol_results: list[SymbolBacktestResult],
) -> PerformanceMetrics | None:
    if not symbol_results:
        return None

    equity = symbol_results[0].simulation.equity_curve
    sessions = pd.DatetimeIndex(equity.index.normalize().unique())
    splits = generate_walk_forward_splits(
        sessions,
        train_days=config.walk_forward.train_days,
        test_days=config.walk_forward.test_days,
    )
    if not splits:
        return None

    test_segments: list[pd.Series] = []
    for split in splits:
        mask = (equity.index.normalize() >= split.test_start) & (equity.index.normalize() <= split.test_end)
        segment = equity.loc[mask]
        if not segment.empty:
            test_segments.append(segment)

    if not test_segments:
        return None

    oos_equity = pd.concat(test_segments).sort_index()
    oos_equity = oos_equity[~oos_equity.index.duplicated(keep="first")]
    return calculate_metrics(oos_equity, periods_per_year=periods_per_year(config.timeframe))


def _calculate_regime_metrics(
    config: BacktestRunConfig,
    benchmarks: list[str],
    repo: BarRepository,
    symbol_results: list[SymbolBacktestResult],
) -> dict[str, PerformanceMetrics]:
    if not benchmarks or not symbol_results:
        return {}

    try:
        benchmark = repo.read_bars(benchmarks[0], start=config.start, end=config.end, timeframe=Timeframe.ONE_MINUTE)
    except (FileNotFoundError, ValueError):
        return {}

    regimes = classify_trend_vol_regime(resample_bars(benchmark, config.timeframe))
    equity = symbol_results[0].simulation.equity_curve
    aligned = pd.DataFrame({"equity": equity}).join(regimes.rename("regime"), how="inner")
    output: dict[str, PerformanceMetrics] = {}
    for regime, group in aligned.groupby("regime"):
        if len(group) >= 2:
            output[str(regime)] = calculate_metrics(
                group["equity"],
                periods_per_year=periods_per_year(config.timeframe),
            )
    return output
