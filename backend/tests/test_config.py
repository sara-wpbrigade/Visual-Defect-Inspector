"""Tests for settings validation and report-writer selection."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import (
    DEFAULT_MAX_AUDIO_BYTES,
    DEFAULT_MAX_AUDIO_SECONDS,
    DEFAULT_MAX_TRANSCRIPT_CHARS,
    DEFAULT_REPORT_MAX_ATTEMPTS,
    DEFAULT_REPORT_TIMEOUT_SECONDS,
    DEFAULT_WHISPER_COMPUTE_TYPE,
    DEFAULT_WHISPER_DEVICE,
    DEFAULT_WHISPER_MODEL,
    DetectorKind,
    ReportWriterKind,
    Settings,
)
from app.models.factory import GEMINI_SETTINGS_ERROR, create_report_writer
from app.models.template_writer import TemplateReportWriter

GEMINI_ENV_VARS = ("DETECTOR", "GEMINI_API_KEY", "GEMINI_MODEL", "REPORT_WRITER")


@pytest.fixture(autouse=True)
def clear_settings_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Isolate settings tests from the developer's environment and .env file."""
    for name in GEMINI_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    yield


def make_settings(**overrides: Any) -> Settings:
    """Build settings from the isolated test directory."""
    return Settings(**overrides)


def test_template_writer_needs_no_gemini_credentials() -> None:
    """A fresh clone can run the offline detector and writer with no key."""
    settings = make_settings(
        report_writer=ReportWriterKind.TEMPLATE,
        detector=DetectorKind.PATCHCORE,
    )
    assert settings.gemini_api_key is None
    assert isinstance(create_report_writer(settings), TemplateReportWriter)


def test_gemini_writer_requires_both_credentials() -> None:
    """Selecting Gemini without a key and model fails loudly."""
    with pytest.raises(ValidationError) as error:
        make_settings(report_writer=ReportWriterKind.GEMINI)
    message = str(error.value)
    assert "GEMINI_API_KEY" in message
    assert "GEMINI_MODEL" in message


def test_gemini_writer_reports_the_missing_key_only() -> None:
    """The error names exactly what is absent."""
    with pytest.raises(ValidationError) as error:
        make_settings(
            report_writer=ReportWriterKind.GEMINI,
            gemini_model="gemini-2.5-flash",
        )
    message = str(error.value)
    assert "GEMINI_API_KEY" in message
    assert "GEMINI_MODEL" not in message


def test_gemini_writer_accepts_a_key_and_model() -> None:
    """Complete Gemini settings are valid."""
    settings = make_settings(
        report_writer=ReportWriterKind.GEMINI,
        gemini_api_key=SecretStr("test-key"),
        gemini_model="gemini-2.5-flash",
    )
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "test-key"
    assert settings.gemini_model == "gemini-2.5-flash"


def test_gemini_detector_requires_credentials_even_with_the_template_writer() -> None:
    """A Gemini detector needs a key and model even when reports are offline."""
    with pytest.raises(ValidationError) as error:
        make_settings(
            report_writer=ReportWriterKind.TEMPLATE,
            detector=DetectorKind.GEMINI,
        )
    message = str(error.value)
    assert "GEMINI_API_KEY" in message
    assert "GEMINI_MODEL" in message
    assert "DETECTOR=gemini" in message


def test_empty_gemini_key_is_rejected() -> None:
    """A key that is present but blank is not a key."""
    with pytest.raises(ValidationError):
        make_settings(
            report_writer=ReportWriterKind.TEMPLATE,
            gemini_api_key=SecretStr(""),
        )


def test_report_defaults_are_explicit() -> None:
    """The offline report tuning has stable documented defaults."""
    settings = make_settings(
        report_writer=ReportWriterKind.TEMPLATE,
        detector=DetectorKind.PATCHCORE,
    )
    assert settings.report_timeout_seconds == DEFAULT_REPORT_TIMEOUT_SECONDS
    assert settings.report_max_attempts == DEFAULT_REPORT_MAX_ATTEMPTS
    assert settings.max_transcript_chars == DEFAULT_MAX_TRANSCRIPT_CHARS


def test_audio_and_whisper_defaults_are_explicit() -> None:
    """The voice-note tuning has stable documented defaults."""
    settings = make_settings(
        report_writer=ReportWriterKind.TEMPLATE,
        detector=DetectorKind.PATCHCORE,
    )
    assert settings.max_audio_bytes == DEFAULT_MAX_AUDIO_BYTES
    assert settings.max_audio_seconds == DEFAULT_MAX_AUDIO_SECONDS
    assert settings.whisper_model == DEFAULT_WHISPER_MODEL
    assert settings.whisper_device == DEFAULT_WHISPER_DEVICE
    assert settings.whisper_compute_type == DEFAULT_WHISPER_COMPUTE_TYPE


def test_factory_rejects_inconsistent_gemini_settings() -> None:
    """Bypassed validation still cannot build a Gemini writer without credentials."""
    settings = Settings.model_construct(
        report_writer=ReportWriterKind.GEMINI,
        gemini_api_key=None,
        gemini_model=None,
    )
    with pytest.raises(ValueError, match=GEMINI_SETTINGS_ERROR):
        create_report_writer(settings)
