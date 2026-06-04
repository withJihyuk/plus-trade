"""US market session state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

import pandas_market_calendars as mcal
from zoneinfo import ZoneInfo


class MarketState(StrEnum):
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    OPEN = "open"
    AFTER_CLOSE = "after_close"


@dataclass(frozen=True)
class MarketSessionState:
    calendar: str
    state: MarketState
    checked_at: datetime
    market_open: datetime | None
    market_close: datetime | None


class MarketCalendar:
    def __init__(self, calendar_name: str = "NYSE") -> None:
        self.calendar_name = calendar_name
        self.calendar = mcal.get_calendar(calendar_name)
        self.market_tz = ZoneInfo("America/New_York")

    def current_state(self, *, now: datetime | None = None) -> MarketSessionState:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        current = current.astimezone(UTC)

        local_now = current.astimezone(self.market_tz)
        schedule = self.calendar.schedule(
            start_date=local_now.date().isoformat(),
            end_date=local_now.date().isoformat(),
        )

        if schedule.empty:
            return MarketSessionState(
                calendar=self.calendar_name,
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
            calendar=self.calendar_name,
            state=state,
            checked_at=current,
            market_open=market_open,
            market_close=market_close,
        )
