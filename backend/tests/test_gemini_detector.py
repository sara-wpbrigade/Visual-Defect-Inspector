"""Offline unit tests for the Gemini vision detector and its factory wiring."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
from google import genai
from google.genai import errors as genai_errors
from PIL import Image
from pydantic import SecretStr

from app.core.config import DetectorKind, ReportWriterKind, Settings
from app.models import factory as factory_module
from app.models import gemini, gemini_classifier
from app.models.detector import Detection
from app.models.registry import DetectorRegistry

IMAGE_WIDTH = 200
IMAGE_HEIGHT = 100
BOX_2D = [100, 100, 500, 500]


@dataclass(frozen=True)
class CategoryStub:
    """The slice of CategoryConfig that the Gemini detector and factory read."""

    display_name: str = "bottle"
    description: str = "plastic bottle"
    defect_types: tuple[str, ...] = ("crack",)
    checkpoint_path: str = "missing.ckpt"
    min_similarity: float = 0.8


CATEGORY = CategoryStub()


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep settings away from the developer's environment and .env file."""
    for name in ("DETECTOR", "REPORT_WRITER", "GEMINI_API_KEY", "GEMINI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)


class StubResponse:
    """The only attribute the detector reads from a generate_content response."""

    def __init__(self, payload: dict[str, Any]) -> None:
        """Serialize the scripted JSON payload onto ``.text``."""
        self.text = json.dumps(payload)


class StubModels:
    """Replay scripted responses or errors, recording every call."""

    def __init__(self, outcomes: list[Any]) -> None:
        """Store the scripted outcomes and initialize the call log."""
        self._outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> StubResponse:
        """Record the call and return or raise the next scripted outcome."""
        self.calls.append(kwargs)
        outcome = self._outcomes[min(len(self.calls) - 1, len(self._outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class StubClient:
    """A Gemini client whose models endpoint is fully scripted."""

    def __init__(self, outcomes: list[Any]) -> None:
        """Attach a scripted ``models`` endpoint."""
        self.models = StubModels(outcomes)


class RetryableAPIError(genai_errors.APIError):
    """A 503 APIError that carries only a status code, with no HTTP response."""

    def __init__(self, code: int = 503) -> None:
        """Initialize the simulated APIError with an integer status code."""
        Exception.__init__(self, f"{code} simulated API error")
        self.code = code


def pass_answer(confidence: float = 0.95) -> StubResponse:
    """Return a scripted pass verdict."""
    return StubResponse(
        {
            "observations": "The bottle is intact with no visible damage.",
            "verdict": "pass",
            "confidence": confidence,
        }
    )


def make_detector(outcomes: list[Any], **kwargs: Any) -> tuple[gemini.GeminiDetector, StubClient]:
    """Build a detector over a scripted client instead of the real API."""
    client = StubClient(outcomes)
    return gemini.GeminiDetector(client, "test-model", cast(Any, CATEGORY), **kwargs), client


def test_pass_verdict_scores_low_and_returns_an_empty_map() -> None:
    """A pass needs no location data: low score, empty mask, zero heatmap."""
    detector, client = make_detector([pass_answer()])

    result = detector.detect(Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT)))

    assert isinstance(result, Detection)
    assert result.score == pytest.approx(gemini.PASS_SCORE)
    assert result.score < gemini.UNCERTAIN_SCORE
    assert result.mask.dtype == bool
    assert result.mask.shape == (IMAGE_HEIGHT, IMAGE_WIDTH)
    assert not result.mask.any()
    assert result.anomaly_map.dtype == np.float32
    assert result.anomaly_map.shape == (IMAGE_HEIGHT, IMAGE_WIDTH)
    assert not result.anomaly_map.any()
    assert len(client.models.calls) == 1


def test_defect_verdict_paints_the_box_on_the_mask_and_anomaly_map() -> None:
    """A defect scores high and its box becomes mask pixels and heatmap values."""
    detector, _ = make_detector(
        [
            StubResponse(
                {
                    "observations": "A crack runs down the left shoulder.",
                    "verdict": "defect",
                    "confidence": 0.9,
                    "severity": "high",
                    "defect_type": "crack",
                    "boxes": [{"box_2d": BOX_2D, "label": "crack"}],
                }
            )
        ]
    )

    result = detector.detect(Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT)))

    ymin, xmin, ymax, xmax = BOX_2D
    top = ymin * IMAGE_HEIGHT // 1000
    bottom = ymax * IMAGE_HEIGHT // 1000
    left = xmin * IMAGE_WIDTH // 1000
    right = xmax * IMAGE_WIDTH // 1000
    inside = result.mask[top:bottom, left:right]

    assert result.score >= gemini.DEFECT_SCORE_FLOOR
    assert result.score > gemini.UNCERTAIN_SCORE
    assert inside.any()
    assert inside.all()
    # Nothing outside the reported box may be painted.
    assert result.mask.sum() == inside.size
    assert result.anomaly_map.dtype == np.float32
    assert np.allclose(result.anomaly_map[top:bottom, left:right], 0.9)
    assert np.count_nonzero(result.anomaly_map) == inside.size


def test_retries_a_503_and_succeeds_on_the_next_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retryable APIError is retried instead of failing the inspection."""
    monkeypatch.setattr(gemini.time, "sleep", lambda _seconds: None)
    detector, client = make_detector([RetryableAPIError(503), pass_answer()], retries=1)

    result = detector.detect(Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT)))

    assert result.score == pytest.approx(gemini.PASS_SCORE)
    assert len(client.models.calls) == 2


def test_create_detector_builds_gemini_without_a_checkpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Gemini mode ignores the checkpoint path entirely."""
    captured: dict[str, Any] = {}

    class ClientSpy:
        """Record the client arguments instead of opening a connection."""

        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(genai, "Client", ClientSpy)
    missing = tmp_path / "absent.ckpt"
    settings = Settings(
        detector=DetectorKind.GEMINI,
        report_writer=ReportWriterKind.TEMPLATE,
        gemini_api_key=SecretStr("test-key"),
        gemini_model="test-model",
    )

    detector = factory_module.create_detector(
        missing, "cpu", settings=settings, category=cast(Any, CATEGORY)
    )

    assert isinstance(detector, gemini.GeminiDetector)
    assert captured["api_key"] == "test-key"
    assert not missing.exists()


def test_registry_passes_settings_and_category_without_a_checkpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The registry hands its settings and category to the Gemini factory."""
    missing = tmp_path / "absent.ckpt"
    category = CategoryStub(checkpoint_path=str(missing))
    captured: dict[str, Any] = {}
    client_args: dict[str, Any] = {}
    real_create_detector = factory_module.create_detector

    def spy(
        checkpoint_path: Path,
        device: str,
        settings: Settings | None = None,
        category: Any = None,
    ) -> Any:
        captured.update(
            checkpoint_path=checkpoint_path,
            device=device,
            settings=settings,
            category=category,
        )
        return real_create_detector(checkpoint_path, device, settings=settings, category=category)

    class ClientSpy:
        """Record the client arguments instead of opening a connection."""

        def __init__(self, **kwargs: Any) -> None:
            client_args.update(kwargs)

    class CatalogStub:
        """Return one category without loading the on-disk catalog."""

        def get(self, category_id: str) -> CategoryStub:
            assert category_id == "bottle"
            return category

    monkeypatch.setattr(genai, "Client", ClientSpy)
    monkeypatch.setattr(factory_module, "create_detector", spy)
    settings = Settings(
        detector=DetectorKind.GEMINI,
        report_writer=ReportWriterKind.TEMPLATE,
        gemini_api_key=SecretStr("test-key"),
        gemini_model="test-model",
    )

    detector = DetectorRegistry(cast(Any, CatalogStub()), "cpu", settings=settings).get("bottle")

    assert isinstance(detector, gemini.GeminiDetector)
    assert captured["settings"] is settings
    assert captured["category"] is category
    assert captured["checkpoint_path"] == missing
    assert client_args["api_key"] == "test-key"
    assert not missing.exists()


def test_category_classifier_accepts_matching_part_and_rejects_mismatch() -> None:
    """A matching Gemini gate passes min_similarity; a mismatch returns 0.0."""
    category = CategoryStub(min_similarity=0.8)

    class CatalogStub:
        """Return one category without loading the on-disk catalog."""

        def get(self, category_id: str) -> CategoryStub:
            """Return the stub category for bottle."""
            assert category_id == "bottle"
            return category

    match_client = StubClient(
        [StubResponse({"observations": "A clear bottle.", "matches": True, "confidence": 0.7})]
    )
    mismatch_client = StubClient(
        [StubResponse({"observations": "A metal screw.", "matches": False, "confidence": 0.95})]
    )

    match_score = gemini_classifier.GeminiCategoryClassifier(
        match_client, "test-model", cast(Any, CatalogStub())
    ).similarity(Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT)), "bottle")
    mismatch_score = gemini_classifier.GeminiCategoryClassifier(
        mismatch_client, "test-model", cast(Any, CatalogStub())
    ).similarity(Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT)), "bottle")

    assert match_score >= category.min_similarity
    assert mismatch_score == 0.0


def test_create_category_classifier_builds_gemini_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gemini mode builds GeminiCategoryClassifier instead of loading embeddings."""

    class ClientSpy:
        """Record client creation without opening a connection."""

        def __init__(self, **_kwargs: Any) -> None:
            pass

    monkeypatch.setattr(genai, "Client", ClientSpy)
    settings = Settings(
        detector=DetectorKind.GEMINI,
        report_writer=ReportWriterKind.TEMPLATE,
        gemini_api_key=SecretStr("test-key"),
        gemini_model="test-model",
    )

    classifier = factory_module.create_category_classifier(cast(Any, object()), settings)

    assert isinstance(classifier, gemini_classifier.GeminiCategoryClassifier)
