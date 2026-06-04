"""FX rate cache backed by KIS quote data."""

from __future__ import annotations

from plus_trade.config import Settings
from plus_trade.paths import FX_REFERENCE_SYMBOL
from plus_trade.state import FxRateSnapshot, StateStore, utc_now


class FxRateProvider:
    def __init__(self, settings: Settings, store: StateStore) -> None:
        self.settings = settings
        self.store = store

    def get_usd_krw(self, kis: object, *, refresh: bool = False) -> FxRateSnapshot:
        cached = self.store.get_fx_rate(self.settings.fx_base_currency, self.settings.fx_quote_currency)
        if cached and not refresh and cached.is_fresh(self.settings.fx_rate_ttl_seconds):
            return cached

        quote = kis.stock(FX_REFERENCE_SYMBOL).quote()  # type: ignore[attr-defined]
        exchange_rate = getattr(quote, "exchange_rate", None)
        if exchange_rate is None:
            raise RuntimeError(f"KIS quote for {FX_REFERENCE_SYMBOL} did not include exchange_rate")

        snapshot = FxRateSnapshot(
            base_currency=self.settings.fx_base_currency,
            quote_currency=self.settings.fx_quote_currency,
            rate=float(exchange_rate),
            source_symbol=FX_REFERENCE_SYMBOL,
            fetched_at=utc_now(),
        )
        self.store.save_fx_rate(snapshot)
        return snapshot
