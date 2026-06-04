# plus-trade

`plus-trade` is a uv-based Python CLI skeleton for a Korea Investment & Securities
auto-trading service. The first version focuses on operational plumbing:
configuration, KIS client creation, token persistence, US market state, FX cache,
SQLite state, and Discord notifications.

It does not implement trading strategies or place orders.

## Setup

```bash
uv sync
cp .env.example .env
```

Fill in `.env` with the KIS credentials for the mode you want to run.

```dotenv
PLUS_TRADE_ENV=local
PLUS_TRADE_LOG_LEVEL=INFO

KIS_VIRTUAL=true

KIS_REAL_HTS_ID=
KIS_REAL_ACCOUNT_NO=
KIS_REAL_APP_KEY=
KIS_REAL_APP_SECRET=

KIS_VIRTUAL_HTS_ID=
KIS_VIRTUAL_ACCOUNT_NO=
KIS_VIRTUAL_APP_KEY=
KIS_VIRTUAL_APP_SECRET=

FX_BASE_CURRENCY=USD
FX_QUOTE_CURRENCY=KRW
FX_RATE_TTL_SECONDS=3600

DISCORD_WEBHOOK_URL=
```

## Commands

```bash
uv run plus-trade doctor
uv run plus-trade notify-test
uv run plus-trade run --once
uv run plus-trade backtest ingest --universe configs/universes/us-core.yaml --start 2026-01-01 --end 2026-03-31
uv run plus-trade backtest run --config configs/backtests/example.yaml
```

`doctor` initializes local runtime directories and SQLite state, then reports
which credentials and integrations are configured.

`notify-test` sends a Discord message when `DISCORD_WEBHOOK_URL` is present.
Without a webhook it exits successfully as a no-op.

`run --once` creates the KIS client, resolves current NYSE regular-session state,
refreshes the USD/KRW FX cache when stale, persists runtime state, and sends a
Discord summary when a webhook is configured.

`backtest ingest` fetches KIS 1-minute chart data and stores it as local Parquet.
`backtest run` reads only local Parquet data, resamples to the configured
timeframe, applies long-only target-weight strategy signals, next-bar-open fills,
costs, slippage, OOS, and regime summaries.

## Runtime Paths

Runtime files are intentionally fixed in code:

- `var/plus_trade.sqlite3`
- `var/kis_tokens`
- `var/data/bars/1m/{SYMBOL}.parquet`
- `var/logs`

KIS token persistence and refresh is always enabled with `python-kis`
`keep_token=var/kis_tokens`. WebSocket usage is always disabled in v1.

## Testing Policy

Test code is limited to trading strategy validation and backtesting
infrastructure. The current tests cover resampling, fills, costs, metrics,
walk-forward splits, and backtest CLI command construction.
