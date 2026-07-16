# Architecture

`plus-trade` is a CLI-first auto-trading service skeleton. v1 keeps the runtime
small and explicit: no web server, no scheduler daemon, no strategy execution,
and no order placement.

## Modules

- `plus_trade.cli`: Typer command entrypoint for `doctor`, `notify-test`, and
  `run --once`.
- `plus_trade.config`: `.env` and environment variable loading with
  `pydantic-settings`.
- `plus_trade.kis_client`: `PyKis` factory. Token persistence is always enabled
  through `keep_token=var/kis_tokens`; WebSocket is always disabled.
- `plus_trade.market`: NYSE regular-session state using
  `pandas_market_calendars`.
- `plus_trade.fx`: USD/KRW cache sourced from the `exchange_rate` field on the
  KIS quote for the fixed reference symbol `AAPL`. The currency pair is fixed in
  code for v1.
- `plus_trade.state`: SQLite schema and persistence helpers.
- `plus_trade.messaging`: Discord webhook notifier with no-op behavior when the
  webhook is absent.
- `plus_trade.runner`: One operational cycle orchestration.

## Data Flow

`run --once` loads settings, initializes SQLite, creates a KIS client, resolves
market state, refreshes FX if the cached rate is stale, persists state, and sends
a Discord summary when configured. It exits unsuccessfully after persistence and
notification attempts when FX lookup or configured Discord delivery fails.

The command does not place orders. Strategy and order modules should be added
later behind explicit interfaces once strategy validation exists.

## Runtime State

All local runtime state is under `var/`:

- `var/plus_trade.sqlite3`: runtime state, market session observations, FX cache,
  notification history.
- `var/kis_tokens`: `python-kis` token cache.
- `var/logs`: reserved for future file logging.
