# Strategy Development

This document defines the information needed to develop and judge backtest
strategies in `plus-trade`.

## Data And Run Setup

Strategies run against local Parquet bars. The backtest command never calls KIS
or yfinance directly.

```bash
uv run plus-trade backtest ingest-yfinance --universe configs/universes/us-core.yaml --start 2026-01-01 --end 2026-03-31 --timeframe 1h
uv run plus-trade backtest run --config configs/backtests/example.yaml
```

The example config currently uses:

- Universe: `AAPL`, `MSFT`, `NVDA`
- Benchmark regime source: first benchmark in `configs/universes/us-core.yaml`
- Timeframe: `1h`
- Capital: `10000`, split equally across symbols
- Strategy: `MovingAverageCrossStrategy(fast_window=5, slow_window=20)`
- Costs: fee `5bps`, FX spread `10bps`, slippage `5bps`

## Strategy Contract

A strategy is a class configured by `configs/backtests/*.yaml`. It must expose:

```python
def target_weights(self, bars: pd.DataFrame) -> pd.Series:
    ...
```

Rules:

- Input bars contain `timestamp,symbol,open,high,low,close,volume`.
- The returned `Series` index must be timestamps matching the bars.
- Values must be between `0.0` and `1.0`.
- `0.0` means fully in cash for that symbol.
- `1.0` means fully allocated to that symbol.
- v1 is long-only. Short exposure and leverage are not supported.
- The strategy must not use future bars to decide the current target weight.

## Execution Assumptions

- Signals are calculated from the current bar.
- Position changes are filled at the next bar open.
- Fill price includes configured slippage.
- Trading cost includes fee bps and FX spread bps.
- The volume participation cap limits how much of the next bar volume can fill.
- Symbol simulations are run separately, then aggregated into a portfolio equity
  curve.

These assumptions matter because high-frequency signal churn can look profitable
before costs, then fail after slippage, FX spread, and volume limits.

## Output Metrics

- `total return`: end equity divided by start equity minus one.
- `cagr`: annualized return. It can look extreme on short samples.
- `sharpe`: average return per unit of volatility. Negative values mean the
  strategy is losing money after taking risk.
- `sortino`: similar to Sharpe, but focused on downside volatility.
- `mdd`: maximum drawdown from peak equity to trough equity.
- `calmar`: CAGR divided by absolute max drawdown.
- `turnover`: traded notional divided by initial capital.
- `trades`: number of simulated fills.

High turnover is not automatically bad, but it must be justified by strong OOS
performance. If turnover is high and Sharpe is negative, costs and whipsaw are
probably destroying the strategy.

## Walk-Forward OOS And Regime Review

The walk-forward OOS summary runs each test window separately instead of slicing
the full-period equity curve. For each split, the engine passes the train window
to `strategy.fit(train_bars)` when that method exists, then simulates only the
test window and aggregates test-window returns. Strategies without `fit` run as
static strategies, using the train window as indicator warmup context for test
signals.

Treat OOS as more important than in-sample total return. Automatic parameter
search is not built into the engine; implement it inside `fit` when a strategy
needs train-window parameter selection.

Regime breakdown groups portfolio interval returns by benchmark regime:

- `uptrend_low_vol`
- `uptrend_high_vol`
- `sideways_low_vol`
- `sideways_high_vol`
- `downtrend_low_vol`
- `downtrend_high_vol`

A strategy that only makes money in uptrends but loses heavily in sideways or
downtrend regimes is a fragile trend follower. It needs a market filter,
position-size control, stop logic, or a cash regime before it can be considered a
real candidate.

## Development Gate

Before promoting a strategy beyond experiment status, check:

- It beats cash and buy-and-hold on portfolio-level OOS results.
- OOS Sharpe and Sortino are positive after costs.
- Max drawdown is acceptable for the target capital.
- Turnover is explainable and not purely caused by noisy signals.
- Regime losses are bounded, especially in `downtrend_high_vol`.
- Performance is not dependent on one symbol.
- Parameters are stable across nearby values.
- Raising fee, FX spread, and slippage does not immediately destroy the result.

Automated test code, when added, belongs only to strategy validation. Runtime,
broker, notification, and plumbing code should continue to be verified by manual
checks unless this policy changes.
