"""Historical bar data loading, persistence, and KIS ingestion."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from plus_trade.backtest.models import BacktestRunConfig, Timeframe, UniverseConfig
from plus_trade.backtest.resample import normalize_bars
from plus_trade.paths import BAR_DATA_DIR, ensure_runtime_dirs


def load_universe_config(path: Path) -> UniverseConfig:
    with path.open("r", encoding="utf-8") as file:
        return UniverseConfig.model_validate(yaml.safe_load(file))


def load_backtest_config(path: Path) -> BacktestRunConfig:
    with path.open("r", encoding="utf-8") as file:
        return BacktestRunConfig.model_validate(yaml.safe_load(file))


class BarRepository:
    def __init__(self, root: Path = BAR_DATA_DIR) -> None:
        ensure_runtime_dirs()
        self.root = root

    def path_for(self, symbol: str, timeframe: Timeframe = Timeframe.ONE_MINUTE) -> Path:
        return self.root / timeframe.value / f"{symbol.upper()}.parquet"

    def write_bars(self, symbol: str, bars: pd.DataFrame, timeframe: Timeframe = Timeframe.ONE_MINUTE) -> Path:
        path = self.path_for(symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)
        incoming = normalize_bars(bars)
        incoming = incoming[incoming["symbol"] == symbol.upper()]

        if path.exists():
            existing = pd.read_parquet(path)
            merged = pd.concat([existing, incoming], ignore_index=True)
        else:
            merged = incoming

        merged = (
            normalize_bars(merged)
            .drop_duplicates(subset=["symbol", "timestamp"], keep="last")
            .sort_values(["symbol", "timestamp"])
            .reset_index(drop=True)
        )
        merged.to_parquet(path, index=False)
        return path

    def read_bars(
        self,
        symbol: str,
        *,
        start: str | date | None = None,
        end: str | date | None = None,
        timeframe: Timeframe = Timeframe.ONE_MINUTE,
    ) -> pd.DataFrame:
        path = self.path_for(symbol, timeframe)
        if not path.exists():
            raise FileNotFoundError(f"missing bar data for {symbol.upper()}: {path}")

        bars = normalize_bars(pd.read_parquet(path))
        if start is not None:
            start_ts = pd.Timestamp(start, tz="UTC")
            bars = bars[bars["timestamp"] >= start_ts]
        if end is not None:
            end_ts = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
            bars = bars[bars["timestamp"] < end_ts]
        if bars.empty:
            raise ValueError(f"no bars for {symbol.upper()} between {start} and {end}")
        return bars.reset_index(drop=True)


class KisChartIngestor:
    def __init__(self, kis: Any, repository: BarRepository) -> None:
        self.kis = kis
        self.repository = repository

    def ingest_symbol(self, symbol: str, *, start: date, end: date) -> Path:
        stock = self.kis.stock(symbol.upper())
        chart = stock.chart(start=start, end=end, period=1)
        rows: list[dict[str, Any]] = []

        for bar in chart.bars:
            timestamp = getattr(bar, "time", None) or getattr(bar, "date", None)
            rows.append(
                {
                    "timestamp": pd.to_datetime(timestamp, utc=True),
                    "symbol": symbol.upper(),
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": float(bar.volume),
                }
            )

        if not rows:
            raise ValueError(f"KIS returned no bars for {symbol.upper()} between {start} and {end}")

        return self.repository.write_bars(symbol.upper(), pd.DataFrame(rows), Timeframe.ONE_MINUTE)
