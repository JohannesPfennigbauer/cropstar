from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DRIVER_URL_PREFIX = "postgresql+psycopg://"


class Settings(BaseSettings):
    """Runtime configuration, read from `CROPSTAR_*` environment variables."""

    model_config = SettingsConfigDict(env_prefix="CROPSTAR_")

    # Development unlocks conveniences such as demo data; never set it on a real instance.
    environment: Literal["development", "production"] = "production"
    database_url: str = f"{_DRIVER_URL_PREFIX}cropstar:cropstar@localhost:5432/cropstar"
    host: str = "0.0.0.0"
    port: int = 8000

    # Origin users reach Cropstar under; used for links in emails.
    public_base_url: str = "http://localhost:3000"
    registration_open: bool = True
    session_lifetime_days: int = 30
    # Browsers accept Secure cookies on http://localhost, so this stays on outside tests.
    cookie_secure: bool = True

    # Email is optional. Without a host, password reset falls back to the Instance Operator.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "Cropstar <noreply@localhost>"
    smtp_starttls: bool = True

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, url: str) -> str:
        # Hosting panels such as Coolify hand out plain `postgres://` URLs; accept them as-is.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return _DRIVER_URL_PREFIX + url.removeprefix(prefix)
        return url

    @field_validator("public_base_url")
    @classmethod
    def _strip_trailing_slash(cls, url: str) -> str:
        return url.rstrip("/")
