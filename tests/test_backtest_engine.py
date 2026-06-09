from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
import yaml

from plus_trade.backtest.data import BarRepository
from plus_trade.backtest.engine import run_backtest
from plus_trade.backtest.fills import simulate_target_weight_portfolio
from plus_trade.backtest.models import Timeframe


class FitAwareStrategy:
    fit_calls = 0

    def fit(self, train_bars: pd.DataFrame) -> "FitAwareStrategy":
        type(self).fit_calls += 1
        if train_bars.empty:
            raise AssertionError("walk-forward fit received no train bars")
        return self

    def target_weights(self, bars: pd.DataFrame) -> pd.Series:
        timestamps = pd.to_datetime(bars.sort_values("timestamp")["timestamp"], utc=True)
        return pd.Series(1.0, index=timestamps, name="target_weight")


class BacktestEngineTest(unittest.TestCase):
    def test_zero_quantity_fills_are_not_recorded_as_trades(self) -> None:
        bars = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-01-01 14:30", periods=3, freq="h", tz="UTC"),
                "symbol": ["TST", "TST", "TST"],
                "open": [100.0, 100.0, 100.0],
                "high": [100.0, 100.0, 100.0],
                "low": [100.0, 100.0, 100.0],
                "close": [100.0, 100.0, 100.0],
                "volume": [1_000.0, 0.0, 1_000.0],
            }
        )
        weights = pd.Series(1.0, index=bars["timestamp"], name="target_weight")

        simulation = simulate_target_weight_portfolio(
            bars,
            weights,
            initial_capital=1_000,
            fee_bps=0,
            fx_spread_bps=0,
            slippage_bps=0,
            volume_participation_cap=0.05,
        )

        self.assertEqual(len(simulation.fills), 1)
        self.assertTrue((simulation.fills["filled_qty"] > 0).all())

    def test_walk_forward_oos_fits_strategy_on_train_window(self) -> None:
        FitAwareStrategy.fit_calls = 0
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repository = BarRepository(root=root / "bars")
            timestamps = pd.date_range("2026-01-01 14:30", periods=4, freq="D", tz="UTC")
            repository.write_bars(
                "TST",
                pd.DataFrame(
                    {
                        "timestamp": timestamps,
                        "symbol": ["TST"] * len(timestamps),
                        "open": [100.0, 100.0, 100.0, 100.0],
                        "high": [100.0, 100.0, 100.0, 100.0],
                        "low": [100.0, 100.0, 100.0, 100.0],
                        "close": [100.0, 100.0, 100.0, 100.0],
                        "volume": [1_000.0, 1_000.0, 1_000.0, 1_000.0],
                    }
                ),
                Timeframe.ONE_HOUR,
            )

            universe_path = root / "universe.yaml"
            universe_path.write_text(yaml.safe_dump({"symbols": ["TST"], "benchmarks": []}), encoding="utf-8")
            config_path = root / "backtest.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "universe": str(universe_path),
                        "start": "2026-01-01",
                        "end": "2026-01-04",
                        "timeframe": "1h",
                        "initial_capital": 1_000,
                        "walk_forward": {"train_days": 2, "test_days": 2},
                        "strategy": {
                            "module": "tests.test_backtest_engine",
                            "name": "FitAwareStrategy",
                            "params": {},
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = run_backtest(config_path, repository=repository)

        self.assertIsNotNone(result.oos_metrics)
        self.assertEqual(FitAwareStrategy.fit_calls, 1)


if __name__ == "__main__":
    unittest.main()
