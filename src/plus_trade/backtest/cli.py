"""Backtest CLI commands."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from plus_trade.backtest.data import BarRepository, KisChartIngestor, load_universe_config
from plus_trade.backtest.engine import BacktestResult, run_backtest
from plus_trade.config import load_settings
from plus_trade.kis_client import create_kis_client


backtest_app = typer.Typer(no_args_is_help=True, help="Backtesting data and simulation commands")
console = Console()


@backtest_app.command()
def ingest(
    universe: Path = typer.Option(..., "--universe", exists=True, readable=True),
    start: str = typer.Option(..., "--start", help="Start date in YYYY-MM-DD format."),
    end: str = typer.Option(..., "--end", help="End date in YYYY-MM-DD format."),
) -> None:
    """Fetch 1-minute KIS chart data and persist it as local Parquet."""

    settings = load_settings()
    kis = create_kis_client(settings)
    repository = BarRepository()
    ingestor = KisChartIngestor(kis, repository)
    universe_config = load_universe_config(universe)
    symbols = sorted(set(universe_config.symbols + universe_config.benchmarks))
    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")

    table = Table(title="backtest ingest")
    table.add_column("symbol")
    table.add_column("path")

    for symbol in symbols:
        path = ingestor.ingest_symbol(symbol, start=start_date, end=end_date)
        table.add_row(symbol, str(path))

    console.print(table)


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
    summary = Table(title="backtest summary")
    summary.add_column("symbol")
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
        oos = Table(title="walk-forward OOS summary")
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
        regime_table = Table(title="regime breakdown")
        regime_table.add_column("regime")
        regime_table.add_column("total return")
        regime_table.add_column("sharpe")
        regime_table.add_column("mdd")
        for regime, metrics in result.regime_metrics.items():
            regime_table.add_row(regime, _pct(metrics.total_return), f"{metrics.sharpe:.2f}", _pct(metrics.max_drawdown))
        console.print(regime_table)


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"{name} must use YYYY-MM-DD format") from exc
