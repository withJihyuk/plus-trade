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
uv run plus-trade backtest ingest-yfinance --universe configs/universes/us-core.yaml --start 2026-01-01 --end 2026-03-31 --timeframe 1h
uv run plus-trade backtest ingest --universe configs/universes/us-core.yaml --start-time 09:30 --end-time 16:00
uv run plus-trade backtest import-bars --input data/AAPL.csv --symbol AAPL
uv run plus-trade backtest run --config configs/backtests/example.yaml
```

`doctor` initializes local runtime directories and SQLite state, then reports
which credentials and integrations are configured.

`notify-test` sends a Discord message when `DISCORD_WEBHOOK_URL` is present.
Without a webhook it exits successfully as a no-op.

`run --once` creates the KIS client, resolves current NYSE regular-session state,
refreshes the USD/KRW FX cache when stale, persists runtime state, and sends a
Discord summary when a webhook is configured.

`backtest ingest-yfinance` fetches historical OHLCV bars from yfinance and stores
them as local Parquet. The default backtest timeframe is `1h`, which is the
practical free-data compromise for multi-month intraday validation. yfinance
intraday availability is constrained by Yahoo's retention limits; if a request
is outside that range, the command fails with the provider error surfaced.

`backtest ingest` fetches today's KIS 1-minute chart data and stores it as local
Parquet. The KIS minute endpoint is intraday-only, so it is an operational data
path, not the default historical backtest source. `backtest import-bars` remains
available for external CSV or Parquet data. `backtest run` reads only local
Parquet data, applies long-only target-weight strategy signals, next-bar-open
fills, costs, slippage, OOS, and regime summaries.

## Runtime Paths

Runtime files are intentionally fixed in code:

- `var/plus_trade.sqlite3`
- `var/kis_tokens`
- `var/data/bars/1m/{SYMBOL}.parquet`
- `var/data/bars/1h/{SYMBOL}.parquet`
- `var/logs`

KIS token persistence and refresh is always enabled with `python-kis`
`keep_token=var/kis_tokens`. WebSocket usage is always disabled in v1.

## Backtesting Data Contract

Imported bars must contain:

```text
timestamp,symbol,open,high,low,close,volume
```

Timestamps are normalized to UTC and persisted under `var/data/bars/1m`.
Backtest execution never calls KIS or yfinance directly. It reads local Parquet
for the configured timeframe first, then falls back to resampling local `1m`
data when the configured timeframe cache is absent.
