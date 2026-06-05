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

## Backtest Output

`portfolio summary` is the first result to read. It aggregates all configured
symbols after equal capital allocation. `symbol breakdown` shows whether the
portfolio result is broad-based or driven by one name.

Key fields:

- `total return`: total portfolio gain or loss over the configured period.
- `cagr`: annualized return. Short backtests can make this look extreme.
- `sharpe` / `sortino`: risk-adjusted return. Negative values mean the strategy
  lost money after taking risk.
- `mdd`: maximum drawdown from peak equity to trough equity.
- `calmar`: CAGR divided by absolute max drawdown.
- `turnover`: traded notional divided by initial capital.
- `trades`: simulated fill count.

The current example strategy is only a pipeline check. If it prints a negative
portfolio return, negative Sharpe, high turnover, and losses in sideways or
downtrend regimes, read that as a strategy failure, not a data or engine failure.
It means the moving-average sample is getting whipsawed and paying too much in
costs for the signal quality.

`portfolio walk-forward OOS summary` is more important than the full-period
summary when judging overfit. `portfolio regime breakdown` shows where the
strategy makes or loses money by market state. A strategy that only works in
`uptrend_*` regimes needs a filter, cash rule, or risk control before it is a
real candidate.

See `docs/strategy-development.md` for the strategy interface, execution
assumptions, metric definitions, and promotion checklist.

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
