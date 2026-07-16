"""Runtime orchestration for one-shot and daemon commands."""

from __future__ import annotations

from dataclasses import dataclass

from plus_trade.config import Settings
from plus_trade.fx import FxRateProvider
from plus_trade.kis_client import create_kis_client, describe_kis_mode
from plus_trade.market import MARKET_NAME, MarketSessionState, current_market_state
from plus_trade.messaging import DiscordNotifier, NotificationResult
from plus_trade.state import FxRateSnapshot, StateStore


@dataclass(frozen=True)
class RunOnceResult:
    market: MarketSessionState
    fx_rate: FxRateSnapshot | None
    fx_error: str | None
    notification: NotificationResult
    success: bool


def run_once(settings: Settings, store: StateStore) -> RunOnceResult:
    store.initialize()

    kis = create_kis_client(settings)
    mode = describe_kis_mode(settings)
    market = current_market_state()
    store.record_market_state(
        calendar=MARKET_NAME,
        state=market.state.value,
        market_open=market.market_open,
        market_close=market.market_close,
    )

    fx_rate: FxRateSnapshot | None = None
    fx_error: str | None = None
    try:
        fx_rate = FxRateProvider(settings, store).get_usd_krw(kis)
    except Exception as exc:  # noqa: BLE001 - run loop should persist and notify operational failures.
        fx_error = str(exc)

    store.set_runtime_state(
        "last_run_once",
        {
            "market_state": market.state.value,
            "kis_virtual": mode.virtual,
            "account_no": mode.account_no,
            "fx_rate": fx_rate.rate if fx_rate else None,
            "fx_error": fx_error,
        },
    )

    webhook_url = settings.discord_webhook_url.get_secret_value() if settings.discord_webhook_url else None
    message_lines = [
        f"mode={'virtual' if mode.virtual else 'real'}",
        f"account={mode.account_no}",
        f"market={market.state.value}",
    ]
    if fx_rate:
        message_lines.append(
            f"fx={fx_rate.base_currency}/{fx_rate.quote_currency} {fx_rate.rate:.4f}"
        )
    if fx_error:
        message_lines.append(f"fx_error={fx_error}")

    notification = DiscordNotifier(webhook_url).send(
        title="plus-trade run-once",
        message="\n".join(message_lines),
    )
    store.record_notification(
        event_type="run_once",
        success=notification.success,
        message=notification.detail,
    )

    return RunOnceResult(
        market=market,
        fx_rate=fx_rate,
        fx_error=fx_error,
        notification=notification,
        success=fx_error is None and notification.success,
    )
