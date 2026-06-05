"""Historical bar data loading, persistence, and market data ingestion."""

from __future__ import annotations

from datetime import date, time, timedelta
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


class BarImporter:
    def __init__(self, repository: BarRepository) -> None:
        self.repository = repository

    def import_file(self, path: Path, *, symbol: str, file_format: str | None = None) -> Path:
        format_name = (file_format or path.suffix.lstrip(".")).lower()
        if format_name == "csv":
            bars = pd.read_csv(path)
        elif format_name in {"parquet", "pq"}:
            bars = pd.read_parquet(path)
        else:
            raise ValueError("bar import format must be csv or parquet")

        bars = normalize_bars(bars)
        bars["symbol"] = symbol.upper()
        return self.repository.write_bars(symbol.upper(), bars, Timeframe.ONE_MINUTE)


class KisChartIngestor:
    def __init__(self, kis: Any, repository: BarRepository) -> None:
        self.kis = kis
        self.repository = repository

    def ingest_symbol(self, symbol: str, *, start_time: time | None = None, end_time: time | None = None) -> Path:
        stock = self.kis.stock(symbol.upper())
        chart = stock.chart(start=start_time, end=end_time, period=1)
        rows: list[dict[str, Any]] = []

        for bar in chart.bars:
            timestamp = getattr(bar, "time_kst", None) or getattr(bar, "time", None) or getattr(bar, "date", None)
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
            raise ValueError(f"KIS returned no intraday bars for {symbol.upper()}")

        return self.repository.write_bars(symbol.upper(), pd.DataFrame(rows), Timeframe.ONE_MINUTE)


class YFinanceBarIngestor:
    def __init__(self, repository: BarRepository) -> None:
        self.repository = repository

    def ingest_symbol(
        self,
        symbol: str,
        *,
        start: date,
        end: date,
        timeframe: Timeframe,
        timeout: float = 20,
    ) -> Path:
        if end < start:
            raise ValueError("end date must be greater than or equal to start date")

        symbol = symbol.upper()
        frames: list[pd.DataFrame] = []
        for chunk_start, chunk_end in self._chunk_ranges(start, end, timeframe):
            frame = self._download_chunk(
                symbol,
                start=chunk_start,
                end=chunk_end,
                timeframe=timeframe,
                timeout=timeout,
            )
            if not frame.empty:
                frames.append(frame)

        if not frames:
            raise ValueError(
                f"yfinance returned no {timeframe.value} bars for {symbol} "
                f"between {start.isoformat()} and {end.isoformat()}"
            )

        bars = pd.concat(frames, ignore_index=True)
        return self.repository.write_bars(symbol, bars, timeframe)

    def _chunk_ranges(self, start: date, end: date, timeframe: Timeframe) -> list[tuple[date, date]]:
        chunk_days = 7 if timeframe is Timeframe.ONE_MINUTE else 59
        final_exclusive = end + timedelta(days=1)
        chunks: list[tuple[date, date]] = []
        chunk_start = start
        while chunk_start < final_exclusive:
            chunk_end = min(chunk_start + timedelta(days=chunk_days), final_exclusive)
            chunks.append((chunk_start, chunk_end))
            chunk_start = chunk_end
        return chunks

    def _download_chunk(
        self,
        symbol: str,
        *,
        start: date,
        end: date,
        timeframe: Timeframe,
        timeout: float,
    ) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("yfinance is not installed; run `uv sync` first") from exc

        try:
            previous_hide_exceptions = yf.config.debug.hide_exceptions
            yf.config.debug.hide_exceptions = False
            data = yf.Ticker(symbol).history(
                start=start.isoformat(),
                end=end.isoformat(),
                interval=timeframe.value,
                auto_adjust=False,
                prepost=False,
                actions=False,
                repair=False,
                timeout=timeout,
            )
        except Exception as exc:  # yfinance wraps Yahoo response failures inconsistently across versions.
            raise RuntimeError(
                f"failed to download {symbol} {timeframe.value} bars from yfinance "
                f"for {start.isoformat()} to {end.isoformat()}: {exc}"
            ) from exc
        finally:
            if "previous_hide_exceptions" in locals():
                yf.config.debug.hide_exceptions = previous_hide_exceptions

        return self._normalize_yfinance_bars(symbol, data)

    def _normalize_yfinance_bars(self, symbol: str, data: pd.DataFrame | None) -> pd.DataFrame:
        if data is None or data.empty:
            return pd.DataFrame(columns=["timestamp", "symbol", "open", "high", "low", "close", "volume"])

        frame = data.copy()
        if isinstance(frame.columns, pd.MultiIndex):
            frame = self._flatten_yfinance_columns(symbol, frame)

        rename_map = {
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        missing = [column for column in rename_map if column not in frame.columns]
        if missing:
            raise ValueError(f"yfinance response for {symbol} missing columns: {', '.join(missing)}")

        bars = frame.rename(columns=rename_map).loc[:, list(rename_map.values())].reset_index()
        timestamp_column = bars.columns[0]
        bars = bars.rename(columns={timestamp_column: "timestamp"})
        bars["symbol"] = symbol
        bars = bars.dropna(subset=["timestamp", "open", "high", "low", "close"])
        bars["volume"] = bars["volume"].fillna(0)
        return normalize_bars(bars)

    def _flatten_yfinance_columns(self, symbol: str, frame: pd.DataFrame) -> pd.DataFrame:
        for level in range(frame.columns.nlevels):
            values = frame.columns.get_level_values(level)
            if symbol in values:
                return frame.xs(symbol, axis=1, level=level, drop_level=True)
        return frame.droplevel([level for level in range(1, frame.columns.nlevels)], axis=1)
