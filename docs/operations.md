# Operations

## Environment

Use `.env.example` as the source of truth for environment variables. Runtime
paths, token behavior, WebSocket behavior, and FX reference symbol are fixed in
code.

`KIS_VIRTUAL=true` runs against the virtual configuration and requires both real
and virtual KIS credentials because `python-kis` accepts one active account while
also using real and virtual key sets on the same client.

`KIS_VIRTUAL=false` runs against real credentials only.

## Tokens

`python-kis` token persistence is always enabled:

```python
PyKis(..., keep_token=var/kis_tokens, use_websocket=False)
```

The library saves and reuses tokens, and refreshes expired cached tokens when a
valid token is requested. Treat `var/kis_tokens` as sensitive local state.

## Manual Checks

Run these before any strategy or order code is added:

```bash
uv run plus-trade doctor
uv run plus-trade notify-test
uv run plus-trade run --once
uv run plus-trade backtest ingest --universe configs/universes/us-core.yaml --start 2026-01-01 --end 2026-03-31
uv run plus-trade backtest run --config configs/backtests/example.yaml
```

`doctor` should run without secrets and show missing credentials explicitly.
`notify-test` should no-op when `DISCORD_WEBHOOK_URL` is empty. `run --once`
requires valid KIS credentials and may call the KIS quote API to refresh FX.

`backtest ingest` requires valid KIS credentials and writes 1-minute bars to
`var/data/bars/1m`. `backtest run` never calls KIS; it fails with a clear missing
data message if required Parquet files are absent.

## Discord

Discord is configured only by `DISCORD_WEBHOOK_URL`. If it is empty, notification
calls are skipped successfully. There are no event-level notification toggles in
v1.

## FX

FX means USD/KRW exchange-rate state. v1 uses the `exchange_rate` value from the
KIS quote for the fixed reference symbol `AAPL`. The rate is cached in SQLite for
`FX_RATE_TTL_SECONDS`.

## Testing Policy

Do not add general unit tests for live-operation infrastructure. Tests are
allowed for strategy validation, backtesting, and signal verification. Current
backtest tests cover only deterministic calculation behavior and CLI command
construction.

## Backtest Assumptions

- Source data is KIS 1-minute OHLCV, stored locally as Parquet.
- 5-minute and 15-minute bars are resampled from the 1-minute source.
- v1 strategies are long-only target-weight strategies.
- Signals use current bar close data only; fills occur at the next bar open.
- Fee bps, FX spread bps, slippage bps, and volume participation cap are defined
  in `configs/backtests/*.yaml`.
