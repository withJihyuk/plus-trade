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

FX_RATE_TTL_SECONDS=3600

DISCORD_WEBHOOK_URL=
```

## Commands

```bash
uv run plus-trade doctor
uv run plus-trade notify-test
uv run plus-trade run --once
```

`doctor` initializes local runtime directories and SQLite state, then reports
which credentials and integrations are configured.

`notify-test` sends a Discord message when `DISCORD_WEBHOOK_URL` is present.
Without a webhook it exits successfully as a no-op.

`run --once` creates the KIS client, resolves current NYSE regular-session state,
refreshes the USD/KRW FX cache when stale, persists runtime state, and sends a
Discord summary when a webhook is configured. FX lookup or configured Discord
delivery failures are persisted and reported with a non-zero exit code.

## Runtime Paths

Runtime files are intentionally fixed in code:

- `var/plus_trade.sqlite3`
- `var/kis_tokens`
- `var/logs`

These paths and `.env` are resolved from the repository root, independent of the
shell's current working directory. The v1 FX pair is fixed to USD/KRW; only its
cache TTL is configurable.

KIS token persistence and refresh is always enabled with `python-kis`
`keep_token=var/kis_tokens`. WebSocket usage is always disabled in v1.

## Testing Policy

No general infrastructure tests are included. Test code should only be added
when trading strategy validation, backtesting, or signal verification is added.
