from plus_trade.backtest.costs import adjusted_fill_price, transaction_cost
from plus_trade.backtest.models import OrderSide


def test_transaction_cost_includes_fee_and_fx_spread_bps() -> None:
    assert transaction_cost(10_000, fee_bps=5, fx_spread_bps=10) == 15


def test_slippage_adjusts_buy_and_sell_prices_against_trader() -> None:
    assert adjusted_fill_price(100, OrderSide.BUY, slippage_bps=10) == 100.1
    assert adjusted_fill_price(100, OrderSide.SELL, slippage_bps=10) == 99.9
