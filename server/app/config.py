from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "stormfront"

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = Field(default="dev-only-change-me", min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 30

    cors_origins: list[str] = ["http://localhost:5173"]

    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
