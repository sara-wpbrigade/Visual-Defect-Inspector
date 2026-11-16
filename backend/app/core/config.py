"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from the environment or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: SecretStr = Field(min_length=1)
    gemini_model: str = Field(min_length=1)


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings object, creating it on first use."""
    # Values come from the environment at runtime, which pyright cannot see.
    return Settings()  # pyright: ignore[reportCallIssue]
