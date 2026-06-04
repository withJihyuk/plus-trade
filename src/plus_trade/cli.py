"""Command line interface."""

from __future__ import annotations

from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from plus_trade.config import load_settings
from plus_trade.messaging import DiscordNotifier
from plus_trade.paths import DB_PATH, KIS_TOKEN_DIR, LOG_DIR, ensure_runtime_dirs
from plus_trade.runner import run_once
from plus_trade.state import StateStore


app = typer.Typer(no_args_is_help=True, help="plus-trade auto-trading service skeleton")
console = Console()


def _load_settings_or_exit():
    try:
        return load_settings()
    except ValidationError as exc:
        console.print("[red]Invalid configuration[/red]")
        for error in exc.errors():
            console.print(f"- {error['msg']}")
        raise typer.Exit(code=1) from exc


def _status(value: bool) -> str:
    return "[green]ok[/green]" if value else "[yellow]missing[/yellow]"


@app.command()
def doctor() -> None:
    """Check local runtime configuration without placing orders."""

    settings = _load_settings_or_exit()
    ensure_runtime_dirs()
    store = StateStore()
    store.initialize()
    missing_credentials = settings.missing_required_credentials()
    active_account = settings.active_account_no if not missing_credentials else "-"

    table = Table(title="plus-trade doctor")
    table.add_column("check")
    table.add_column("value")
    table.add_column("status")

    table.add_row("environment", settings.plus_trade_env.value, "ok")
    table.add_row("log level", settings.plus_trade_log_level, "ok")
    table.add_row("trading mode", "virtual" if settings.kis_virtual else "real", "ok")
    table.add_row("active account", active_account, _status(not missing_credentials))
    table.add_row(
        "KIS credentials",
        "all required values present" if not missing_credentials else ", ".join(missing_credentials),
        _status(not missing_credentials),
    )
    table.add_row("database", str(DB_PATH), _status(DB_PATH.exists()))
    table.add_row("token dir", str(KIS_TOKEN_DIR), _status(KIS_TOKEN_DIR.exists()))
    table.add_row("log dir", str(LOG_DIR), _status(LOG_DIR.exists()))
    table.add_row("discord", "configured" if settings.discord_enabled else "not configured", "ok")
    table.add_row(
        "fx",
        f"{settings.fx_base_currency}/{settings.fx_quote_currency}, ttl={settings.fx_rate_ttl_seconds}s",
        "ok",
    )

    console.print(table)


@app.command("notify-test")
def notify_test() -> None:
    """Send a Discord test notification when webhook is configured."""

    settings = _load_settings_or_exit()
    webhook_url = settings.discord_webhook_url.get_secret_value() if settings.discord_webhook_url else None
    result = DiscordNotifier(webhook_url).send(
        title="plus-trade notify-test",
        message="Discord webhook is reachable from plus-trade.",
    )
    StateStore().initialize()
    StateStore().record_notification(
        event_type="notify_test",
        success=result.success,
        message=result.detail,
    )

    if not result.sent:
        console.print("[yellow]Discord webhook is not configured; skipped.[/yellow]")
        return
    if result.success:
        console.print("[green]Discord notification sent.[/green]")
        return

    console.print(f"[red]Discord notification failed:[/red] {result.detail}")
    raise typer.Exit(code=1)


@app.command()
def run(
    once: Annotated[
        bool,
        typer.Option("--once", help="Run one operational cycle and exit."),
    ] = False,
) -> None:
    """Run the service loop."""

    if not once:
        console.print("[yellow]Daemon loop is not implemented yet. Use --once for v1.[/yellow]")
        raise typer.Exit(code=1)

    settings = _load_settings_or_exit()
    try:
        result = run_once(settings, StateStore())
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"market={result.market.state.value}")
    if result.fx_rate:
        console.print(
            f"fx={result.fx_rate.base_currency}/{result.fx_rate.quote_currency} {result.fx_rate.rate:.4f}"
        )
    if result.notification.sent:
        console.print(f"discord={result.notification.detail}")
    else:
        console.print("discord=not configured")
