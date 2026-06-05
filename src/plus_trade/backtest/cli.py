"""Backtest CLI commands."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from plus_trade.backtest.data import (
    BarImporter,
    BarRepository,
    KisChartIngestor,
    YFinanceBarIngestor,
    load_universe_config,
)
from plus_trade.backtest.engine import BacktestResult, run_backtest
from plus_trade.backtest.models import Timeframe
from plus_trade.config import load_settings
from plus_trade.kis_client import create_kis_client


backtest_app = typer.Typer(no_args_is_help=True, help="Backtesting data and simulation commands")
console = Console()


@backtest_app.command()
def ingest(
    universe: Path = typer.Option(..., "--universe", exists=True, readable=True),
    start_time: str | None = typer.Option(None, "--start-time", help="Intraday start time in HH:MM format."),
    end_time: str | None = typer.Option(None, "--end-time", help="Intraday end time in HH:MM format."),
) -> None:
    """Fetch today's 1-minute KIS chart data and persist it as local Parquet."""

    settings = load_settings()
    kis = create_kis_client(settings)
    repository = BarRepository()
    ingestor = KisChartIngestor(kis, repository)
    universe_config = load_universe_config(universe)
    symbols = sorted(set(universe_config.symbols + universe_config.benchmarks))
    parsed_start_time = _parse_time(start_time, "start-time") if start_time else None
    parsed_end_time = _parse_time(end_time, "end-time") if end_time else None

    table = Table(title="backtest ingest")
    table.add_column("symbol")
    table.add_column("path")

    for symbol in symbols:
        path = ingestor.ingest_symbol(symbol, start_time=parsed_start_time, end_time=parsed_end_time)
        table.add_row(symbol, str(path))

    console.print(table)


@backtest_app.command("ingest-yfinance")
def ingest_yfinance(
    universe: Path = typer.Option(..., "--universe", exists=True, readable=True),
    start: str = typer.Option(..., "--start", help="Inclusive start date in YYYY-MM-DD format."),
    end: str = typer.Option(..., "--end", help="Inclusive end date in YYYY-MM-DD format."),
    timeframe: Timeframe = typer.Option(Timeframe.ONE_HOUR, "--timeframe"),
    timeout: float = typer.Option(20, "--timeout", min=1, help="Per-request timeout in seconds."),
) -> None:
    """Fetch yfinance OHLCV bars and persist them as local Parquet."""

    repository = BarRepository()
    ingestor = YFinanceBarIngestor(repository)
    universe_config = load_universe_config(universe)
    symbols = sorted(set(universe_config.symbols + universe_config.benchmarks))
    parsed_start = _parse_date(start, "start")
    parsed_end = _parse_date(end, "end")

    table = Table(title="backtest ingest-yfinance")
    table.add_column("symbol")
    table.add_column("timeframe")
    table.add_column("path")

    try:
        for symbol in symbols:
            path = ingestor.ingest_symbol(
                symbol,
                start=parsed_start,
                end=parsed_end,
                timeframe=timeframe,
                timeout=timeout,
            )
            table.add_row(symbol, timeframe.value, str(path))
    except (RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(table)


@backtest_app.command("import-bars")
def import_bars(
    input_path: Path = typer.Option(..., "--input", exists=True, readable=True, file_okay=True, dir_okay=False),
    symbol: str = typer.Option(..., "--symbol"),
    file_format: str | None = typer.Option(None, "--format", help="Input format: csv or parquet. Defaults to extension."),
) -> None:
    """Import historical OHLCV bars into the local Parquet cache."""

    path = BarImporter(BarRepository()).import_file(input_path, symbol=symbol, file_format=file_format)
    console.print(f"imported {symbol.upper()} bars into {path}")


@backtest_app.command("run")
def run_command(
    config: Path = typer.Option(..., "--config", exists=True, readable=True),
) -> None:
    """Run a vector backtest from local Parquet data."""

    try:
        result = run_backtest(config)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_result(result)


def _print_result(result: BacktestResult) -> None:
    portfolio = Table(title="portfolio summary")
    portfolio.add_column("total return")
    portfolio.add_column("cagr")
    portfolio.add_column("sharpe")
    portfolio.add_column("sortino")
    portfolio.add_column("mdd")
    portfolio.add_column("calmar")
    portfolio.add_column("turnover")
    portfolio.add_column("trades")
    metrics = result.portfolio.metrics
    portfolio.add_row(
        _pct(metrics.total_return),
        _pct(metrics.cagr),
        f"{metrics.sharpe:.2f}",
        f"{metrics.sortino:.2f}",
        _pct(metrics.max_drawdown),
        f"{metrics.calmar:.2f}",
        _pct(result.portfolio.turnover),
        str(result.portfolio.trade_count),
    )
    console.print(portfolio)

    summary = Table(title="symbol breakdown")
    summary.add_column("symbol")
    summary.add_column("capital")
    summary.add_column("total return")
    summary.add_column("cagr")
    summary.add_column("sharpe")
    summary.add_column("sortino")
    summary.add_column("mdd")
    summary.add_column("calmar")
    summary.add_column("turnover")
    summary.add_column("trades")

    for symbol_result in result.symbols:
        metrics = symbol_result.metrics
        summary.add_row(
            symbol_result.symbol,
            f"{symbol_result.allocated_capital:.2f}",
            _pct(metrics.total_return),
            _pct(metrics.cagr),
            f"{metrics.sharpe:.2f}",
            f"{metrics.sortino:.2f}",
            _pct(metrics.max_drawdown),
            f"{metrics.calmar:.2f}",
            _pct(symbol_result.simulation.turnover),
            str(len(symbol_result.simulation.fills)),
        )

    console.print(summary)

    if result.oos_metrics:
        oos = Table(title="portfolio walk-forward OOS summary")
        oos.add_column("total return")
        oos.add_column("cagr")
        oos.add_column("sharpe")
        oos.add_column("sortino")
        oos.add_column("mdd")
        oos.add_column("calmar")
        metrics = result.oos_metrics
        oos.add_row(
            _pct(metrics.total_return),
            _pct(metrics.cagr),
            f"{metrics.sharpe:.2f}",
            f"{metrics.sortino:.2f}",
            _pct(metrics.max_drawdown),
            f"{metrics.calmar:.2f}",
        )
        console.print(oos)

    if result.regime_metrics:
        regime_table = Table(title="portfolio regime breakdown")
        regime_table.add_column("regime")
        regime_table.add_column("total return")
        regime_table.add_column("sharpe")
        regime_table.add_column("mdd")
        for regime, metrics in result.regime_metrics.items():
            regime_table.add_row(regime, _pct(metrics.total_return), f"{metrics.sharpe:.2f}", _pct(metrics.max_drawdown))
        console.print(regime_table)


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _parse_time(value: str, name: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"{name} must use HH:MM format") from exc


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"{name} must use YYYY-MM-DD format") from exc
