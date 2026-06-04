from typer.testing import CliRunner

from plus_trade.cli import app


def test_backtest_help_renders() -> None:
    result = CliRunner().invoke(app, ["backtest", "--help"])

    assert result.exit_code == 0
    assert "Backtesting data and simulation commands" in result.output
