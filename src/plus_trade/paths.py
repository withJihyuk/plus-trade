"""Project-local runtime paths."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VAR_DIR = PROJECT_ROOT / "var"
DB_PATH = VAR_DIR / "plus_trade.sqlite3"
LOG_DIR = VAR_DIR / "logs"
KIS_TOKEN_DIR = VAR_DIR / "kis_tokens"
FX_REFERENCE_SYMBOL = "AAPL"
FX_BASE_CURRENCY = "USD"
FX_QUOTE_CURRENCY = "KRW"


def ensure_runtime_dirs() -> None:
    for path in (VAR_DIR, LOG_DIR, KIS_TOKEN_DIR):
        path.mkdir(parents=True, exist_ok=True)
