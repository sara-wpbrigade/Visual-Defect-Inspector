"""Application settings loaded from environment variables."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATEGORIES_DIR = BACKEND_ROOT / "config" / "categories"
DEFAULT_UPLOAD_DIR = BACKEND_ROOT / "data" / "uploads"
DEFAULT_DATABASE_PATH = BACKEND_ROOT / "data" / "inspections.db"
DEFAULT_THUMBNAIL_SIZE = 160
MEGABYTE = 1024 * 1024
DEFAULT_MAX_IMAGE_BYTES = 10 * MEGABYTE
DEFAULT_MAX_IMAGE_PIXELS = 4096 * 4096
DEFAULT_MAX_AUDIO_BYTES = 5 * MEGABYTE
DEFAULT_MAX_AUDIO_SECONDS = 60.0
DEFAULT_WHISPER_MODEL = "base"
DEFAULT_WHISPER_DEVICE = "cpu"
DEFAULT_WHISPER_COMPUTE_TYPE = "int8"
DEFAULT_GEMINI_API_VERSION = "v1beta"
DEFAULT_REPORT_TIMEOUT_SECONDS = 20.0
DEFAULT_REPORT_IMAGE_MAX_SIDE = 1024
DEFAULT_REPORT_INCLUDE_IMAGE = True
DEFAULT_REPORT_MAX_ATTEMPTS = 2
DEFAULT_MAX_TRANSCRIPT_CHARS = 1000
DEFAULT_GEMINI_VISION_VOTES = 1
DEFAULT_GEMINI_VISION_TEMPERATURE = 0.0
DEFAULT_GEMINI_VISION_ZOOM = False
DEFAULT_GEMINI_VISION_VERIFY = False
DEFAULT_GEMINI_VISION_MAX_SIDE = 1536
DEFAULT_GEMINI_VISION_RETRIES = 3
MILLISECONDS_PER_SECOND = 1000

GEMINI_SETTING_NAMES = ("GEMINI_API_KEY", "GEMINI_MODEL")


class ReportWriterKind(StrEnum):
    """Which report wording implementation to use."""

    GEMINI = "gemini"
    TEMPLATE = "template"


class DetectorKind(StrEnum):
    """Which anomaly detector implementation to use."""

    PATCHCORE = "patchcore"
    GEMINI = "gemini"


class Settings(BaseSettings):
    """Runtime configuration, read from the environment or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: Annotated[SecretStr, Field(min_length=1)] | None = None
    gemini_model: Annotated[str, Field(min_length=1)] | None = None

    persona_name: str = Field(default="factory_qc_operator", pattern=r"[a-z][a-z_]{0,40}")
    # Directory that contains per-category JSON files (relative to the repository root)
    categories_dir: Path = DEFAULT_CATEGORIES_DIR
    # Optional comma-separated list of category ids to enable; empty -> enable all found.
    enabled_categories: str = Field(
        default="",
        description="Comma-separated list of category ids to enable; empty means all.",
    )
    detector_device: str = Field(default="auto", min_length=1)
    upload_dir: Path = DEFAULT_UPLOAD_DIR
    database_path: Path = DEFAULT_DATABASE_PATH
    thumbnail_size: int = Field(default=DEFAULT_THUMBNAIL_SIZE, gt=0)
    max_image_bytes: int = Field(default=DEFAULT_MAX_IMAGE_BYTES, gt=0)
    max_image_pixels: int = Field(default=DEFAULT_MAX_IMAGE_PIXELS, gt=0)
    max_audio_bytes: int = Field(default=DEFAULT_MAX_AUDIO_BYTES, gt=0)
    max_audio_seconds: float = Field(default=DEFAULT_MAX_AUDIO_SECONDS, gt=0)
    whisper_model: str = Field(default=DEFAULT_WHISPER_MODEL, min_length=1)
    whisper_device: str = Field(default=DEFAULT_WHISPER_DEVICE, min_length=1)
    whisper_compute_type: str = Field(default=DEFAULT_WHISPER_COMPUTE_TYPE, min_length=1)

    report_writer: ReportWriterKind = ReportWriterKind.GEMINI
    gemini_api_version: str = Field(default=DEFAULT_GEMINI_API_VERSION, min_length=1)
    report_timeout_seconds: float = Field(default=DEFAULT_REPORT_TIMEOUT_SECONDS, gt=0)
    report_image_max_side: int = Field(default=DEFAULT_REPORT_IMAGE_MAX_SIDE, gt=0)
    report_include_image: bool = DEFAULT_REPORT_INCLUDE_IMAGE
    report_max_attempts: int = Field(default=DEFAULT_REPORT_MAX_ATTEMPTS, ge=1)
    max_transcript_chars: int = Field(default=DEFAULT_MAX_TRANSCRIPT_CHARS, gt=0)

    detector: DetectorKind = DetectorKind.GEMINI
    gemini_vision_votes: int = Field(default=DEFAULT_GEMINI_VISION_VOTES, ge=1)
    gemini_vision_temperature: float = Field(
        default=DEFAULT_GEMINI_VISION_TEMPERATURE, ge=0.0, le=2.0
    )
    gemini_vision_zoom: bool = DEFAULT_GEMINI_VISION_ZOOM
    gemini_vision_verify: bool = DEFAULT_GEMINI_VISION_VERIFY
    gemini_vision_max_side: int = Field(default=DEFAULT_GEMINI_VISION_MAX_SIDE, gt=0)
    gemini_vision_retries: int = Field(default=DEFAULT_GEMINI_VISION_RETRIES, ge=0)

    def enabled_category_ids(self) -> list[str]:
        """Return the category ids named in the environment, or an empty list for all."""
        return [part.strip() for part in self.enabled_categories.split(",") if part.strip()]

    @model_validator(mode="after")
    def check_gemini_credentials(self) -> Self:
        """Require the Gemini key and model only when Gemini is selected."""
        needs_report = self.report_writer is ReportWriterKind.GEMINI
        needs_detector = self.detector is DetectorKind.GEMINI
        if not needs_report and not needs_detector:
            return self
        missing = [
            name
            for name, value in zip(
                GEMINI_SETTING_NAMES, (self.gemini_api_key, self.gemini_model), strict=True
            )
            if value is None
        ]
        if missing:
            if needs_report and needs_detector:
                condition = "REPORT_WRITER=gemini or DETECTOR=gemini"
            elif needs_report:
                condition = "REPORT_WRITER=gemini"
            else:
                condition = "DETECTOR=gemini"
            raise ValueError(f"{', '.join(missing)} required when {condition}")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings object, creating it on first use."""
    # Values come from the environment at runtime, which pyright cannot see.
    return Settings()  # pyright: ignore[reportCallIssue]
