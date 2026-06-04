"""Fill simulation for target-weight strategies."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from plus_trade.backtest.costs import adjusted_fill_price, transaction_cost
from plus_trade.backtest.models import OrderSide
from plus_trade.backtest.resample import normalize_bars


@dataclass(frozen=True)
class PortfolioSimulation:
    fills: pd.DataFrame
    equity_curve: pd.Series
    turnover: float


def _bounded_weight(value: float) -> float:
    if value < 0 or value > 1:
        raise ValueError("target_weight must be between 0.0 and 1.0")
    return value


def simulate_target_weight_fills(
    bars: pd.DataFrame,
    target_weights: pd.Series,
    *,
    initial_capital: float,
    volume_participation_cap: float,
    slippage_bps: float,
) -> pd.DataFrame:
    simulation = simulate_target_weight_portfolio(
        bars,
        target_weights,
        initial_capital=initial_capital,
        fee_bps=0,
        fx_spread_bps=0,
        slippage_bps=slippage_bps,
        volume_participation_cap=volume_participation_cap,
    )
    return simulation.fills


def simulate_target_weight_portfolio(
    bars: pd.DataFrame,
    target_weights: pd.Series,
    *,
    initial_capital: float,
    fee_bps: float,
    fx_spread_bps: float,
    slippage_bps: float,
    volume_participation_cap: float,
) -> PortfolioSimulation:
    normalized = normalize_bars(bars)
    if normalized["symbol"].nunique() != 1:
        raise ValueError("portfolio simulation currently accepts one symbol at a time")

    weights = target_weights.copy()
    weights.index = pd.to_datetime(weights.index, utc=True)

    cash = float(initial_capital)
    shares = 0.0
    fills: list[dict[str, float | str | pd.Timestamp]] = []
    equity_values: list[float] = []
    equity_index: list[pd.Timestamp] = []
    total_turnover = 0.0

    for index, row in normalized.iterrows():
        timestamp = row["timestamp"]
        close_price = float(row["close"])

        if index > 0:
            previous_timestamp = normalized.iloc[index - 1]["timestamp"]
            target_weight = _bounded_weight(float(weights.get(previous_timestamp, 0.0)))
            execution_price = float(row["open"])
            equity_before_fill = cash + shares * execution_price
            desired_shares = (equity_before_fill * target_weight) / execution_price
            requested_qty = desired_shares - shares

            if abs(requested_qty) > 1e-12:
                side = OrderSide.BUY if requested_qty > 0 else OrderSide.SELL
                max_qty = float(row["volume"]) * volume_participation_cap
                filled_qty = min(abs(requested_qty), max_qty)
                signed_qty = filled_qty if side is OrderSide.BUY else -filled_qty
                fill_price = adjusted_fill_price(execution_price, side, slippage_bps=slippage_bps)
                notional = signed_qty * fill_price
                cost = transaction_cost(notional, fee_bps=fee_bps, fx_spread_bps=fx_spread_bps)

                cash -= notional
                cash -= cost
                shares += signed_qty
                total_turnover += abs(notional)
                fills.append(
                    {
                        "timestamp": timestamp,
                        "side": side.value,
                        "requested_qty": abs(requested_qty),
                        "filled_qty": filled_qty,
                        "price": fill_price,
                        "notional": abs(notional),
                        "cost": cost,
                    }
                )

        equity_index.append(timestamp)
        equity_values.append(cash + shares * close_price)

    fills_frame = pd.DataFrame(
        fills,
        columns=["timestamp", "side", "requested_qty", "filled_qty", "price", "notional", "cost"],
    )
    equity_curve = pd.Series(equity_values, index=pd.DatetimeIndex(equity_index), dtype=float)
    return PortfolioSimulation(
        fills=fills_frame,
        equity_curve=equity_curve,
        turnover=total_turnover / initial_capital if initial_capital else 0,
    )
