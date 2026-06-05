"""Vector backtest engine."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from plus_trade.backtest.data import BarRepository, load_backtest_config, load_universe_config
from plus_trade.backtest.fills import PortfolioSimulation, simulate_target_weight_portfolio
from plus_trade.backtest.metrics import calculate_metrics, calculate_metrics_from_returns
from plus_trade.backtest.models import BacktestRunConfig, PerformanceMetrics, Timeframe
from plus_trade.backtest.regime import classify_trend_vol_regime
from plus_trade.backtest.resample import resample_bars
from plus_trade.backtest.walk_forward import generate_walk_forward_splits


class Strategy(Protocol):
    def target_weights(self, bars: pd.DataFrame) -> pd.Series: ...


@dataclass(frozen=True)
class SymbolBacktestResult:
    symbol: str
    allocated_capital: float
    metrics: PerformanceMetrics
    simulation: PortfolioSimulation


@dataclass(frozen=True)
class PortfolioBacktestResult:
    metrics: PerformanceMetrics
    equity_curve: pd.Series
    turnover: float
    trade_count: int


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestRunConfig
    portfolio: PortfolioBacktestResult
    symbols: list[SymbolBacktestResult]
    oos_metrics: PerformanceMetrics | None
    regime_metrics: dict[str, PerformanceMetrics]


def load_strategy(config: BacktestRunConfig) -> Strategy:
    module = importlib.import_module(config.strategy.module)
    strategy_type = getattr(module, config.strategy.name)
    return strategy_type(**config.strategy.params)


def periods_per_year(timeframe: Timeframe) -> int:
    return 252 * timeframe.bars_per_trading_day


def run_backtest(config_path, repository: BarRepository | None = None) -> BacktestResult:
    config = load_backtest_config(config_path)
    universe = load_universe_config(config.universe)
    repo = repository or BarRepository()
    strategy = load_strategy(config)
    symbol_results: list[SymbolBacktestResult] = []
    if not universe.symbols:
        raise ValueError("universe must contain at least one symbol")

    allocated_capital = config.initial_capital / len(universe.symbols)

    for symbol in universe.symbols:
        run_bars = _read_run_bars(repo, symbol, config)
        target_weights = strategy.target_weights(run_bars)
        simulation = simulate_target_weight_portfolio(
            run_bars,
            target_weights,
            initial_capital=allocated_capital,
            fee_bps=config.costs.fee_bps,
            fx_spread_bps=config.costs.fx_spread_bps,
            slippage_bps=config.costs.slippage_bps,
            volume_participation_cap=config.costs.volume_participation_cap,
        )
        metrics = calculate_metrics(simulation.equity_curve, periods_per_year=periods_per_year(config.timeframe))
        symbol_results.append(
            SymbolBacktestResult(
                symbol=symbol,
                allocated_capital=allocated_capital,
                metrics=metrics,
                simulation=simulation,
            )
        )

    portfolio = _build_portfolio_result(config, symbol_results)
    oos_metrics = _calculate_oos_metrics(config, portfolio.equity_curve)
    regime_metrics = _calculate_regime_metrics(config, universe.benchmarks, repo, portfolio.equity_curve)
    return BacktestResult(
        config=config,
        portfolio=portfolio,
        symbols=symbol_results,
        oos_metrics=oos_metrics,
        regime_metrics=regime_metrics,
    )


def _read_run_bars(repo: BarRepository, symbol: str, config: BacktestRunConfig) -> pd.DataFrame:
    try:
        return repo.read_bars(symbol, start=config.start, end=config.end, timeframe=config.timeframe)
    except (FileNotFoundError, ValueError) as target_error:
        if config.timeframe is Timeframe.ONE_MINUTE:
            raise target_error

        try:
            one_minute_bars = repo.read_bars(
                symbol,
                start=config.start,
                end=config.end,
                timeframe=Timeframe.ONE_MINUTE,
            )
        except (FileNotFoundError, ValueError):
            raise target_error
        return resample_bars(one_minute_bars, config.timeframe)


def _build_portfolio_result(
    config: BacktestRunConfig,
    symbol_results: list[SymbolBacktestResult],
) -> PortfolioBacktestResult:
    if not symbol_results:
        raise ValueError("cannot build portfolio without symbol results")

    equity_frame = pd.concat(
        [result.simulation.equity_curve.rename(result.symbol) for result in symbol_results],
        axis=1,
        sort=True,
    )

    for result in symbol_results:
        equity_frame[result.symbol] = equity_frame[result.symbol].ffill().fillna(result.allocated_capital)

    portfolio_equity = equity_frame.sum(axis=1).sort_index()
    turnover_notional = sum(result.simulation.turnover * result.allocated_capital for result in symbol_results)
    turnover = turnover_notional / config.initial_capital if config.initial_capital else 0
    trade_count = sum(len(result.simulation.fills) for result in symbol_results)
    metrics = calculate_metrics(portfolio_equity, periods_per_year=periods_per_year(config.timeframe))
    return PortfolioBacktestResult(
        metrics=metrics,
        equity_curve=portfolio_equity,
        turnover=turnover,
        trade_count=trade_count,
    )


def _calculate_oos_metrics(
    config: BacktestRunConfig,
    equity: pd.Series,
) -> PerformanceMetrics | None:
    if equity.empty:
        return None

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
    portfolio_equity: pd.Series,
) -> dict[str, PerformanceMetrics]:
    if not benchmarks or portfolio_equity.empty:
        return {}

    try:
        benchmark = _read_run_bars(repo, benchmarks[0], config)
    except (FileNotFoundError, ValueError):
        return {}

    regimes = classify_trend_vol_regime(benchmark)
    interval_returns = portfolio_equity.pct_change().dropna().rename("return")
    aligned = pd.DataFrame({"return": interval_returns}).join(regimes.rename("regime"), how="inner")
    output: dict[str, PerformanceMetrics] = {}
    for regime, group in aligned.groupby("regime"):
        if len(group) >= 1:
            output[str(regime)] = calculate_metrics_from_returns(
                group["return"],
                periods_per_year=periods_per_year(config.timeframe),
            )
    return output
