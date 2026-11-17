"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT = (
    BACKEND_ROOT
    / "results"
    / "Patchcore"
    / "MVTecAD"
    / "bottle"
    / "v1"
    / "weights"
    / "lightning"
    / "model.ckpt"
)
DEFAULT_UPLOAD_DIR = BACKEND_ROOT / "data" / "uploads"
MEGABYTE = 1024 * 1024
DEFAULT_MAX_IMAGE_BYTES = 10 * MEGABYTE
DEFAULT_MAX_IMAGE_PIXELS = 4096 * 4096


class Settings(BaseSettings):
    """Runtime configuration, read from the environment or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: SecretStr = Field(min_length=1)
    gemini_model: str = Field(min_length=1)

    persona_name: str = Field(default="factory_qc_operator", pattern=r"[a-z][a-z_]{0,40}")
    checkpoint_path: Path = DEFAULT_CHECKPOINT
    detector_device: str = Field(default="auto", min_length=1)
    upload_dir: Path = DEFAULT_UPLOAD_DIR
    max_image_bytes: int = Field(default=DEFAULT_MAX_IMAGE_BYTES, gt=0)
    max_image_pixels: int = Field(default=DEFAULT_MAX_IMAGE_PIXELS, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings object, creating it on first use."""
    # Values come from the environment at runtime, which pyright cannot see.
    return Settings()  # pyright: ignore[reportCallIssue]
