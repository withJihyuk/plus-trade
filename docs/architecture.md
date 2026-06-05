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
  KIS quote for the fixed reference symbol `AAPL`.
- `plus_trade.state`: SQLite schema and persistence helpers.
- `plus_trade.messaging`: Discord webhook notifier with no-op behavior when the
  webhook is absent.
- `plus_trade.runner`: One operational cycle orchestration.
- `plus_trade.backtest`: Local-Parquet backtesting package for strategy
  validation. It is intentionally separate from the live runner.

## Data Flow

`run --once` loads settings, initializes SQLite, creates a KIS client, resolves
market state, refreshes FX if the cached rate is stale, persists state, and sends
a Discord summary when configured.

The command does not place orders. Strategy and order modules should be added
later behind explicit interfaces once strategy validation exists.

## Backtesting Flow

Backtesting uses provider ingestion only to populate local Parquet. The default
historical path is `plus-trade backtest ingest-yfinance`, which writes native
timeframe bars such as `var/data/bars/1h/{SYMBOL}.parquet`. KIS ingestion remains
available for today's 1-minute intraday bars, and external historical files enter
through `plus-trade backtest import-bars`. `plus-trade backtest run` reads local
Parquet only, so runs are reproducible and do not depend on API availability.

The v1 engine is pandas vector-based. Strategies return long-only target weights
between `0.0` and `1.0`. Signals are generated from the current bar close, and
position changes are filled at the next bar open with fee bps, FX spread bps,
slippage bps, and a bar-volume participation cap.

The console output reports portfolio-level risk-adjusted metrics first, then
symbol breakdowns, walk-forward OOS summary, and portfolio regime breakdown when
benchmark data is present.

## Runtime State

All local runtime state is under `var/`:

- `var/plus_trade.sqlite3`: runtime state, market session observations, FX cache,
  notification history.
- `var/kis_tokens`: `python-kis` token cache.
- `var/data/bars`: Parquet historical bar cache.
- `var/logs`: reserved for future file logging.
