"""Korea Investment & Securities client factory."""

from __future__ import annotations

from dataclasses import dataclass
from pykis import KisAuth, PyKis

from plus_trade.config import Settings
from plus_trade.paths import KIS_TOKEN_DIR, ensure_runtime_dirs


@dataclass(frozen=True)
class KisMode:
    virtual: bool
    account_no: str


def create_kis_client(settings: Settings) -> PyKis:
    settings.require_kis_credentials()
    ensure_runtime_dirs()

    real_auth = KisAuth(
        id=settings.kis_real_hts_id,
        account=settings.kis_real_account_no,
        appkey=settings.kis_real_app_key.get_secret_value(),
        secretkey=settings.kis_real_app_secret.get_secret_value(),
        virtual=False,
    )

    if settings.kis_virtual:
        virtual_auth = KisAuth(
            id=settings.kis_virtual_hts_id,
            account=settings.kis_virtual_account_no,
            appkey=settings.kis_virtual_app_key.get_secret_value(),
            secretkey=settings.kis_virtual_app_secret.get_secret_value(),
            virtual=True,
        )
        return PyKis(real_auth, virtual_auth, use_websocket=False, keep_token=KIS_TOKEN_DIR)

    return PyKis(real_auth, use_websocket=False, keep_token=KIS_TOKEN_DIR)


def describe_kis_mode(settings: Settings) -> KisMode:
    return KisMode(virtual=settings.kis_virtual, account_no=settings.active_account_no)
