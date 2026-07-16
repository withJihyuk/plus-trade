"""US market session state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

import pandas_market_calendars as mcal
from zoneinfo import ZoneInfo


MARKET_NAME = "NYSE"
_MARKET_TIMEZONE = ZoneInfo("America/New_York")
_MARKET_CALENDAR = mcal.get_calendar(MARKET_NAME)


class MarketState(StrEnum):
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    OPEN = "open"
    AFTER_CLOSE = "after_close"


@dataclass(frozen=True)
class MarketSessionState:
    state: MarketState
    checked_at: datetime
    market_open: datetime | None
    market_close: datetime | None


def current_market_state(*, now: datetime | None = None) -> MarketSessionState:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    current = current.astimezone(UTC)

    market_date = current.astimezone(_MARKET_TIMEZONE).date().isoformat()
    schedule = _MARKET_CALENDAR.schedule(start_date=market_date, end_date=market_date)

    if schedule.empty:
        return MarketSessionState(
            state=MarketState.CLOSED,
            checked_at=current,
            market_open=None,
            market_close=None,
        )

    row = schedule.iloc[0]
    market_open = row["market_open"].to_pydatetime().astimezone(UTC)
    market_close = row["market_close"].to_pydatetime().astimezone(UTC)

    if current < market_open:
        state = MarketState.PRE_MARKET
    elif current <= market_close:
        state = MarketState.OPEN
    else:
        state = MarketState.AFTER_CLOSE

    return MarketSessionState(
        state=state,
        checked_at=current,
        market_open=market_open,
        market_close=market_close,
    )
