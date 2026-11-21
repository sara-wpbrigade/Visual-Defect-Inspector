"""Tests for detector and report-writer construction."""

from pathlib import Path
from typing import Any

import pytest
from google import genai
from pydantic import SecretStr

from app.core.config import ReportWriterKind, Settings
from app.models import patchcore, whisper_transcriber
from app.models.factory import create_detector, create_report_writer, create_transcriber
from app.models.gemini_writer import GeminiReportWriter
from app.models.template_writer import TemplateReportWriter

TIMEOUT_SECONDS = 2.5
TIMEOUT_MILLISECONDS = 2500


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep settings tests away from the developer's .env file."""
    monkeypatch.chdir(tmp_path)


def test_create_detector_uses_the_checkpoint_and_device(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The detector is built from the configured path and device."""
    captured: dict[str, Any] = {}

    class DetectorSpy:
        """Record the constructor arguments instead of loading a model."""

        def __init__(self, checkpoint_path: Path, device: str) -> None:
            captured["checkpoint_path"] = checkpoint_path
            captured["device"] = device

    monkeypatch.setattr(patchcore, "PatchCoreDetector", DetectorSpy)
    ckpt = tmp_path / "model.ckpt"
    detector = create_detector(ckpt, "cpu")
    assert isinstance(detector, DetectorSpy)
    assert captured["checkpoint_path"] == ckpt
    assert captured["device"] == "cpu"


def test_create_transcriber_uses_the_whisper_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The transcriber is built from the configured model, device and precision."""
    captured: dict[str, Any] = {}

    class TranscriberSpy:
        """Record the constructor arguments instead of loading a model."""

        def __init__(self, model_size: str, device: str, compute_type: str) -> None:
            captured["model_size"] = model_size
            captured["device"] = device
            captured["compute_type"] = compute_type

    monkeypatch.setattr(whisper_transcriber, "FasterWhisperTranscriber", TranscriberSpy)
    settings = Settings(
        report_writer=ReportWriterKind.TEMPLATE,
        whisper_model="tiny",
        whisper_device="cpu",
        whisper_compute_type="int8",
    )
    transcriber = create_transcriber(settings)
    assert isinstance(transcriber, TranscriberSpy)
    assert captured == {"model_size": "tiny", "device": "cpu", "compute_type": "int8"}


def test_create_writer_returns_the_offline_template() -> None:
    """The template choice never touches the Google SDK."""
    settings = Settings(report_writer=ReportWriterKind.TEMPLATE)
    assert isinstance(create_report_writer(settings), TemplateReportWriter)


def test_create_writer_builds_a_gemini_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gemini settings become a client with the configured timeout in milliseconds."""
    captured: dict[str, Any] = {}

    class ClientSpy:
        """Record the client arguments instead of opening a connection."""

        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(genai, "Client", ClientSpy)
    settings = Settings(
        report_writer=ReportWriterKind.GEMINI,
        gemini_api_key=SecretStr("test-key"),
        gemini_model="test-model",
        gemini_api_version="v1beta",
        report_timeout_seconds=TIMEOUT_SECONDS,
    )
    writer = create_report_writer(settings)
    assert isinstance(writer, GeminiReportWriter)
    assert captured["api_key"] == "test-key"
    http_options = captured["http_options"]
    assert http_options.timeout == TIMEOUT_MILLISECONDS
    assert http_options.api_version == "v1beta"
