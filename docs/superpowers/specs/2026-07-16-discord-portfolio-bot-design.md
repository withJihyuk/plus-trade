# Discord Portfolio Bot Design

## Overview

Replace the current Discord webhook notification with a long-running Discord bot.
The bot serves two user-facing capabilities:

1. Show the current US stock portfolio through `/portfolio`.
2. Send a daily performance report 15 minutes after the NYSE regular session closes.

The report is designed for a Korean user. KRW is the primary display currency,
USD is supplementary, stock prices remain in USD, and profit/loss attribution
separates stock performance from exchange-rate effects.

The bot does not collect intraday portfolio snapshots. It creates one closing
snapshot when the daily report is generated and compares it with the previous
NYSE trading day's closing snapshot.

## Product Behavior

### Discord access

- Run the bot with `plus-trade bot` as a long-lived process.
- Register commands only for `DISCORD_GUILD_ID`.
- Accept `/portfolio` only in `DISCORD_CHANNEL_ID`.
- Post `/portfolio` responses publicly in the configured channel.
- Reject requests from other channels with a private explanatory response.
- Never include the KIS account number or credentials in Discord messages,
  images, logs, or stored report payloads.

### `/portfolio`

When invoked, `/portfolio` fetches the active KIS account's US stock balance and
the current KIS USD/KRW valuation rate. It does not write a performance baseline.

The response includes:

- Total portfolio value: KRW primary, USD secondary.
- US stock valuation and USD cash.
- Total unrealized profit/loss in KRW and USD.
- Total unrealized return percentage.
- Applied USD/KRW valuation rate.
- Holdings with symbol, quantity, current price, average purchase price, market
  value, unrealized profit/loss, and return percentage.
- A PNG containing an asset-allocation chart and a holding-level unrealized
  profit/loss chart.

An empty portfolio produces a cash-oriented status card instead of empty charts.

### Daily report schedule

- Use the NYSE calendar to resolve each trading day's actual close, including
  daylight saving time, holidays, and early closes.
- Generate the report 15 minutes after the regular-session close.
- If the bot starts after that day's scheduled report time, skip the missed
  report and schedule the next NYSE trading day.
- A trading day with no executions still produces a portfolio performance report.
- If no previous consecutive closing snapshot exists, save the current closing
  snapshot as a new baseline and send a `performance tracking baseline created`
  report without daily or cumulative performance figures.

## Data Acquisition

At report time, fetch the following once and persist the normalized result:

- `account.balance(country="US")` for US holdings and USD cash.
- `account.daily_orders(start=trade_date, end=trade_date, country="US")` for
  purchases and sales executed on that NYSE trading date.
- Real-account period profit and fee data when supported by KIS. Virtual accounts
  mark fee-dependent figures as estimated.
- The USD/KRW valuation rate returned by KIS balance or quote data.
- SPY's daily close for the current and previous NYSE trading dates.

Synchronous KIS requests and image rendering run in worker threads. A single
`asyncio.Lock` prevents `/portfolio` and scheduled reporting from querying the
same account concurrently.

KIS responses must be normalized into application-owned immutable models before
performance calculation or Discord rendering:

```text
PortfolioSnapshot
  trade_date
  captured_at
  account_mode
  total_usd
  total_krw
  stock_value_usd
  cash_usd
  usd_krw_rate
  holdings[]

HoldingSnapshot
  symbol
  name
  market
  quantity
  average_price_usd
  current_price_usd
  value_usd
  unrealized_profit_usd
  unrealized_return_rate

TradeExecution
  symbol
  side
  executed_quantity
  executed_price_usd
  executed_amount_usd
  executed_at

DailyPerformance
  trade_date
  status
  estimated
  total_profit_usd
  total_profit_krw
  daily_return_rate
  cumulative_return_rate
  stock_effect_krw
  fx_effect_krw
  cash_other_effect_krw
  spy_return_rate
  excess_return_rate
  contributions[]
```

All monetary calculations use `Decimal`. Conversion to `float` is allowed only
at the chart-rendering boundary.

## Performance Calculation

### Portfolio scope

The report covers only:

- US stock positions in the active KIS account.
- USD cash associated with that account.

KRW cash and non-US assets are excluded. The portfolio is normalized to USD
before KRW attribution is calculated.

### Holding contribution

For each symbol:

```text
USD contribution
  = closing holding value
  + same-day sell proceeds
  - same-day buy cost
  - previous closing holding value
```

This prevents purchases and sales from being classified as investment returns.
Symbols sold completely during the day remain in the contribution list with a
zero closing value.

### Daily attribution

Let:

```text
V0 = previous closing portfolio NAV in USD
V1 = current closing portfolio NAV in USD
FX0 = previous KIS USD/KRW valuation rate
FX1 = current KIS USD/KRW valuation rate
P_usd = sum of holding contributions minus identifiable fees
```

Calculate:

```text
Stock-price effect in KRW = P_usd × FX0
FX effect in KRW          = (V1 - identified external cash flow) × (FX1 - FX0)
KRW investment profit     = stock-price effect + FX effect
Cash/other effect         = actual KRW NAV change - KRW investment profit
Daily return              = KRW investment profit / previous KRW NAV
```

USD cash movement is reconciled against executed purchases, sales, and known
fees. The unexplained remainder represents possible deposits, withdrawals,
dividends, taxes, or unsupported fees. It is shown as `cash/other effect` and is
excluded from investment return.

Mark the report as `estimated` when:

- Cash/other effect exceeds 0.1% of the previous KRW NAV.
- Fee data is unavailable for a virtual account.
- Required KIS values are incomplete but a conservative report can still be
  produced.

Do not silently force attribution components to reconcile to zero.

### Cumulative return

- Start tracking from the first closing baseline created by the bot.
- Chain consecutive daily returns geometrically.
- If the immediately previous NYSE trading day's snapshot is missing, start a new
  tracking segment instead of treating multiple days as one-day performance.
- Do not show a single cumulative figure across a discontinuous segment.

### Benchmark and status

- Compare the portfolio daily return with SPY's previous-close-to-current-close
  return.
- If SPY retrieval fails, omit benchmark fields without failing the portfolio
  report.
- Classify daily status as:

  - `profit`: return greater than `+0.05%`.
  - `loss`: return lower than `-0.05%`.
  - `flat`: otherwise.

## Discord Presentation

### Embed

Use the NYSE trading date in the title, for example:

```text
📊 7월 16일 미국주식 리포트
```

The description is generated from deterministic templates:

- Profit: the portfolio increased.
- Loss: the portfolio decreased.
- Flat: there was no material change.

Embed fields include:

- Total assets in KRW, with USD underneath.
- Today's investment profit/loss in KRW, with USD underneath.
- Daily return and tracked cumulative return.
- Stock-price effect, exchange-rate effect, and cash/other effect.
- Applied USD/KRW valuation rate.
- SPY return and excess return when available.
- Same-day execution summary.
- An `estimated` notice and reason when applicable.

Contribution ordering depends on status:

- Profit: three largest positive contributors.
- Loss: three largest negative contributors.
- Flat: three largest absolute contributors.

Each contribution is displayed in KRW and USD. The one-line summary names only
actual contributing symbols and the observed exchange-rate direction. It does not
infer sectors, news, or causal explanations.

### Colors

Follow Korean financial-service conventions:

- Profit: red.
- Loss: blue.
- Flat: gray.
- Remaining UI: neutral colors suitable for Discord's dark theme.

Color is never the only signal; `수익`, `손실`, or `보합` is always shown as text.

### Attached image

Render a `1200 × 675` PNG named `daily-report-YYYY-MM-DD.png`.

Layout:

- Header: status, daily return, KRW and USD profit/loss, total assets.
- Left panel: holding-level daily contribution bar chart.
- Right panel: closing asset-allocation donut chart.
- Footer: portfolio return versus SPY, stock-price effect, FX effect, and
  cash/other effect.

The image does not contain an intraday line chart, intraday high, or intraday low
because no intraday portfolio snapshots are collected.

## Persistence and Delivery

Extend SQLite with:

- Closing portfolio snapshots keyed by NYSE trading date and tracking segment.
- Holding snapshots keyed by closing snapshot and symbol.
- Normalized trade executions for the report date.
- Calculated daily performance and cumulative return.
- Serialized Discord report payload, generation state, delivery state, retry
  count, and last error.

Persist the calculated report payload before the first Discord send. Retries use
the stored payload and image inputs instead of querying KIS again.

Delivery behavior:

- Retry report generation or delivery up to three times at five-minute intervals.
- Record every final outcome in SQLite.
- If image rendering fails but the financial calculation succeeds, send the
  Embed without the image and mark the report as partially delivered.
- If Discord is connected after final generation failure, send a short failure
  notice without exposing credentials or raw API responses.

Existing databases are upgraded with additive `CREATE TABLE IF NOT EXISTS`
statements. The legacy `notifications` table remains for compatibility but is no
longer written.

## Existing Behavior Changes

- Add dependencies on `discord.py` and `matplotlib`.
- Remove the webhook-only `httpx` dependency.
- Remove `DISCORD_WEBHOOK_URL`, `DiscordNotifier`, and `notify-test`.
- Add `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, and `DISCORD_CHANNEL_ID`.
- Update `doctor` to show bot configuration readiness without printing secrets.
- Remove Discord reporting from `run --once`; its success depends only on its own
  operational work, including FX refresh.
- Do not enable Discord Message Content Intent. Required scopes and permissions
  are `bot`, `applications.commands`, view channel, send messages, embed links,
  and attach files.

## Verification and Acceptance

No automated test files are added for this version. Verification uses mock KIS
objects, CLI smoke runs, and a dedicated Discord test server.

Acceptance scenarios:

- First baseline day.
- Profit, loss, and flat days.
- Buy, sell, full liquidation, and no-trade days.
- Exchange-rate increase and decrease.
- Unexplained cash movement and estimated attribution.
- Empty portfolio.
- Missing SPY data.
- Image-rendering failure with Embed fallback.
- Allowed and rejected Discord channels.
- Report delivery retry and final failure recording.
- Existing SQLite database upgrade.
- Clean compile, locked dependency installation, package build, `doctor`,
  `run --once`, and `git diff --check`.

## Explicit Limitations

- No intraday portfolio performance curve or intraday high/low statistics.
- No guaranteed classification of deposits, withdrawals, dividends, taxes, or
  every broker fee because the current KIS SDK does not expose a complete cash
  ledger.
- The exchange rate is the KIS valuation rate, not guaranteed to be a live spot
  FX rate.
- Accurate daily and cumulative performance requires consecutive NYSE closing
  snapshots while the bot is running.
