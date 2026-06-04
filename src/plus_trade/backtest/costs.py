"""Trading cost and slippage helpers."""

from __future__ import annotations

from plus_trade.backtest.models import OrderSide


def bps_to_rate(value: float) -> float:
    return value / 10_000


def transaction_cost(notional: float, *, fee_bps: float, fx_spread_bps: float) -> float:
    return abs(notional) * bps_to_rate(fee_bps + fx_spread_bps)


def adjusted_fill_price(open_price: float, side: OrderSide, *, slippage_bps: float) -> float:
    rate = bps_to_rate(slippage_bps)
    if side is OrderSide.BUY:
        return open_price * (1 + rate)
    return open_price * (1 - rate)
