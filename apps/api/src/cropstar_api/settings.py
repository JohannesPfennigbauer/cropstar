from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from `CROPSTAR_*` environment variables."""

    model_config = SettingsConfigDict(env_prefix="CROPSTAR_")

    database_url: str = "postgresql+psycopg://cropstar:cropstar@localhost:5432/cropstar"
    host: str = "0.0.0.0"
    port: int = 8000
