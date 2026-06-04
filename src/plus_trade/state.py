"""SQLite-backed runtime state."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from plus_trade.paths import DB_PATH, ensure_runtime_dirs


def utc_now() -> datetime:
    return datetime.now(UTC)


def encode_dt(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def decode_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@dataclass(frozen=True)
class FxRateSnapshot:
    base_currency: str
    quote_currency: str
    rate: float
    source_symbol: str
    fetched_at: datetime

    def is_fresh(self, ttl_seconds: int, *, now: datetime | None = None) -> bool:
        current = now or utc_now()
        return current - self.fetched_at <= timedelta(seconds=ttl_seconds)


class StateStore:
    def __init__(self, path: Path = DB_PATH) -> None:
        ensure_runtime_dirs()
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                create table if not exists runtime_state (
                    key text primary key,
                    value text not null,
                    updated_at text not null
                );

                create table if not exists market_sessions (
                    id integer primary key autoincrement,
                    calendar text not null,
                    state text not null,
                    market_open text,
                    market_close text,
                    checked_at text not null
                );

                create table if not exists fx_rates (
                    base_currency text not null,
                    quote_currency text not null,
                    rate real not null,
                    source_symbol text not null,
                    fetched_at text not null,
                    primary key (base_currency, quote_currency)
                );

                create table if not exists notifications (
                    id integer primary key autoincrement,
                    event_type text not null,
                    success integer not null,
                    message text not null,
                    created_at text not null
                );
                """
            )

    def set_runtime_state(self, key: str, value: Mapping[str, Any] | str) -> None:
        payload = value if isinstance(value, str) else json.dumps(value, ensure_ascii=True, sort_keys=True)
        with self.connect() as connection:
            connection.execute(
                """
                insert into runtime_state (key, value, updated_at)
                values (?, ?, ?)
                on conflict(key) do update set
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, payload, encode_dt(utc_now())),
            )

    def record_market_state(
        self,
        *,
        calendar: str,
        state: str,
        market_open: datetime | None,
        market_close: datetime | None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                insert into market_sessions (calendar, state, market_open, market_close, checked_at)
                values (?, ?, ?, ?, ?)
                """,
                (
                    calendar,
                    state,
                    encode_dt(market_open) if market_open else None,
                    encode_dt(market_close) if market_close else None,
                    encode_dt(utc_now()),
                ),
            )

    def get_fx_rate(self, base_currency: str, quote_currency: str) -> FxRateSnapshot | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                select base_currency, quote_currency, rate, source_symbol, fetched_at
                from fx_rates
                where base_currency = ? and quote_currency = ?
                """,
                (base_currency, quote_currency),
            ).fetchone()

        if row is None:
            return None

        return FxRateSnapshot(
            base_currency=row["base_currency"],
            quote_currency=row["quote_currency"],
            rate=float(row["rate"]),
            source_symbol=row["source_symbol"],
            fetched_at=decode_dt(row["fetched_at"]),
        )

    def save_fx_rate(self, snapshot: FxRateSnapshot) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                insert into fx_rates (base_currency, quote_currency, rate, source_symbol, fetched_at)
                values (?, ?, ?, ?, ?)
                on conflict(base_currency, quote_currency) do update set
                    rate = excluded.rate,
                    source_symbol = excluded.source_symbol,
                    fetched_at = excluded.fetched_at
                """,
                (
                    snapshot.base_currency,
                    snapshot.quote_currency,
                    snapshot.rate,
                    snapshot.source_symbol,
                    encode_dt(snapshot.fetched_at),
                ),
            )

    def record_notification(self, *, event_type: str, success: bool, message: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                insert into notifications (event_type, success, message, created_at)
                values (?, ?, ?, ?)
                """,
                (event_type, int(success), message, encode_dt(utc_now())),
            )
