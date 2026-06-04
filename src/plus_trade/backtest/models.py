"""Backtesting domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Timeframe(StrEnum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"

    @property
    def pandas_rule(self) -> str:
        return {
            Timeframe.ONE_MINUTE: "1min",
            Timeframe.FIVE_MINUTES: "5min",
            Timeframe.FIFTEEN_MINUTES: "15min",
        }[self]


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float


@dataclass(frozen=True)
class WalkForwardSplit:
    train_start: Any
    train_end: Any
    test_start: Any
    test_end: Any


class UniverseConfig(BaseModel):
    symbols: list[str]
    benchmarks: list[str] = Field(default_factory=lambda: ["SPY", "QQQ"])
    calendar: str = "NYSE"


class WalkForwardConfig(BaseModel):
    train_days: int = Field(default=60, ge=1)
    test_days: int = Field(default=20, ge=1)


class CostConfig(BaseModel):
    fee_bps: float = Field(default=5.0, ge=0)
    fx_spread_bps: float = Field(default=10.0, ge=0)
    slippage_bps: float = Field(default=5.0, ge=0)
    volume_participation_cap: float = Field(default=0.05, gt=0, le=1)


class StrategyConfig(BaseModel):
    module: str = "plus_trade.backtest.strategies.example"
    name: str = "MovingAverageCrossStrategy"
    params: dict[str, Any] = Field(default_factory=dict)


class BacktestRunConfig(BaseModel):
    universe: Path
    start: str
    end: str
    timeframe: Timeframe = Timeframe.FIVE_MINUTES
    initial_capital: float = Field(default=10_000.0, gt=0)
    costs: CostConfig = Field(default_factory=CostConfig)
    walk_forward: WalkForwardConfig = Field(default_factory=WalkForwardConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
