"""Project-local runtime paths."""

from pathlib import Path


PROJECT_ROOT = Path.cwd()
VAR_DIR = PROJECT_ROOT / "var"
DB_PATH = VAR_DIR / "plus_trade.sqlite3"
LOG_DIR = VAR_DIR / "logs"
KIS_TOKEN_DIR = VAR_DIR / "kis_tokens"
BAR_DATA_DIR = VAR_DIR / "data" / "bars"
FX_REFERENCE_SYMBOL = "AAPL"


def ensure_runtime_dirs() -> None:
    for path in (VAR_DIR, LOG_DIR, KIS_TOKEN_DIR, BAR_DATA_DIR):
        path.mkdir(parents=True, exist_ok=True)
