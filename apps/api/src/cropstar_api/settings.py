from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DRIVER_URL_PREFIX = "postgresql+psycopg://"


class Settings(BaseSettings):
    """Runtime configuration, read from `CROPSTAR_*` environment variables."""

    model_config = SettingsConfigDict(env_prefix="CROPSTAR_")

    database_url: str = f"{_DRIVER_URL_PREFIX}cropstar:cropstar@localhost:5432/cropstar"
    host: str = "0.0.0.0"
    port: int = 8000

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, url: str) -> str:
        # Hosting panels such as Coolify hand out plain `postgres://` URLs; accept them as-is.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return _DRIVER_URL_PREFIX + url.removeprefix(prefix)
        return url
