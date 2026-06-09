"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "supply_chain"
    postgres_user: str = "sc_admin"
    postgres_password: str = "sc_secure_password"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    data_raw_dir: str = "data/raw"
    data_processed_dir: str = "data/processed"
    forecast_horizon_months: int = 12
    random_seed: int = 42

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def raw_data_path(self) -> Path:
        return PROJECT_ROOT / self.data_raw_dir

    @property
    def processed_data_path(self) -> Path:
        return PROJECT_ROOT / self.data_processed_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()
