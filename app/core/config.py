"""Application settings loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FinTrack"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    secret_key: str = "dev-insecure-secret-key-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    bcrypt_rounds: int = 12

    database_url: str = "postgresql+asyncpg://fintrack:fintrack@localhost:5432/fintrack"
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: list[str] = ["http://localhost:8000"]

    login_rate_limit: int = 5
    login_rate_window: int = 300

    exchange_api_url: str = "https://open.er-api.com/v6/latest/USD"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
