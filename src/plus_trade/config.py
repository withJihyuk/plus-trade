"""Environment-backed application settings."""

from enum import StrEnum

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeEnv(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    plus_trade_env: RuntimeEnv = Field(default=RuntimeEnv.LOCAL, alias="PLUS_TRADE_ENV")
    plus_trade_log_level: str = Field(default="INFO", alias="PLUS_TRADE_LOG_LEVEL")

    kis_virtual: bool = Field(default=True, alias="KIS_VIRTUAL")

    kis_real_hts_id: str | None = Field(default=None, alias="KIS_REAL_HTS_ID")
    kis_real_account_no: str | None = Field(default=None, alias="KIS_REAL_ACCOUNT_NO")
    kis_real_app_key: SecretStr | None = Field(default=None, alias="KIS_REAL_APP_KEY")
    kis_real_app_secret: SecretStr | None = Field(default=None, alias="KIS_REAL_APP_SECRET")

    kis_virtual_hts_id: str | None = Field(default=None, alias="KIS_VIRTUAL_HTS_ID")
    kis_virtual_account_no: str | None = Field(default=None, alias="KIS_VIRTUAL_ACCOUNT_NO")
    kis_virtual_app_key: SecretStr | None = Field(default=None, alias="KIS_VIRTUAL_APP_KEY")
    kis_virtual_app_secret: SecretStr | None = Field(default=None, alias="KIS_VIRTUAL_APP_SECRET")

    fx_base_currency: str = Field(default="USD", alias="FX_BASE_CURRENCY")
    fx_quote_currency: str = Field(default="KRW", alias="FX_QUOTE_CURRENCY")
    fx_rate_ttl_seconds: int = Field(default=3600, alias="FX_RATE_TTL_SECONDS", ge=1)

    discord_webhook_url: SecretStr | None = Field(default=None, alias="DISCORD_WEBHOOK_URL")

    def require_kis_credentials(self) -> None:
        missing = self.missing_required_credentials()
        if missing:
            mode = "virtual" if self.kis_virtual else "real"
            fields = ", ".join(missing)
            raise ValueError(f"missing KIS {mode} credentials: {fields}")

    def missing_required_credentials(self) -> list[str]:
        real_fields = [
            "kis_real_hts_id",
            "kis_real_account_no",
            "kis_real_app_key",
            "kis_real_app_secret",
        ]
        virtual_fields = [
            "kis_virtual_hts_id",
            "kis_virtual_account_no",
            "kis_virtual_app_key",
            "kis_virtual_app_secret",
        ]

        required = real_fields + virtual_fields if self.kis_virtual else real_fields
        return [field for field in required if not self._has_value(getattr(self, field))]

    @property
    def active_account_no(self) -> str:
        account_no = self.kis_virtual_account_no if self.kis_virtual else self.kis_real_account_no
        if not account_no:
            raise ValueError("active KIS account number is not configured")
        return account_no

    @property
    def discord_enabled(self) -> bool:
        return bool(self.discord_webhook_url and self.discord_webhook_url.get_secret_value())

    @staticmethod
    def _has_value(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, SecretStr):
            return bool(value.get_secret_value().strip())
        if isinstance(value, str):
            return bool(value.strip())
        return bool(value)


def load_settings() -> Settings:
    return Settings()
