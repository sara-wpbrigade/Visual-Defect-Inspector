"""Test doubles and fixed data shared by the test suite."""

import io
import wave
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType

import numpy as np
from PIL import Image

from app.core.categories import CategoryCatalog, CategoryConfig
from app.models.detector import Detection, Detector
from app.models.registry import DetectorRegistry
from app.models.transcriber import Transcript
from app.schemas import ReportDraft, ReportSource
from app.services.report_facts import ReportFacts

PERSONA_DATA = {
    "name": "test_persona",
    "defect_types": ["scratch"],
    "decision_cutoff": 0.5,
    "review_margin": 0.1,
    "severity_bands": {"low_max": 0.01, "medium_max": 0.05},
    "batch_policy": {"reject_min_severity": "low"},
    "on_pass": "accept",
    "on_uncertain": "re_inspect",
    "on_defect": {"low": "rework", "medium": "rework", "high": "reject"},
    "report": {
        "audience": "test operators",
        "tone": "plain and short",
        "language": "English",
    },
    "action_text": {
        "accept": "Accept the item; no action is needed.",
        "rework": "Send the item to rework and re-inspect it after repair.",
        "reject": "Reject the item and remove it from the batch.",
        "re_inspect": "Re-inspect the item manually; the automatic result is too close to call.",
    },
}

CATEGORY_ID = "widget"
OTHER_CATEGORY_ID = "gadget"
CATEGORY_LOW_MAX = 0.01
CATEGORY_MEDIUM_MAX = 0.05
CATEGORY_MIN_SIMILARITY = 0.5


def make_category_config(
    category_id: str = CATEGORY_ID,
    display_name: str = "Widget",
    *,
    defect_types: tuple[str, ...] = ("scratch",),
    low_max: float = CATEGORY_LOW_MAX,
    medium_max: float = CATEGORY_MEDIUM_MAX,
    min_similarity: float = CATEGORY_MIN_SIMILARITY,
) -> CategoryConfig:
    """Return a category config with generic test paths."""
    return CategoryConfig(
        id=category_id,
        display_name=display_name,
        description=f"A test {display_name}.",
        checkpoint_path=Path(f"{category_id}.ckpt"),
        prototype_path=Path(f"{category_id}.npz"),
        min_similarity=min_similarity,
        defect_types=defect_types,
        severity_bands=MappingProxyType({"low_max": low_max, "medium_max": medium_max}),
    )


def make_catalog(*configs: CategoryConfig) -> CategoryCatalog:
    """Build a catalog from the supplied configs."""
    return CategoryCatalog(configs or (make_category_config(),))


class StubDetector:
    """Detector that returns an injected result (or error) without a model."""

    def __init__(self, result: Detection | Exception) -> None:
        """Remember what detect() should do."""
        self._result = result
        self.calls = 0

    def detect(self, image: Image.Image) -> Detection:
        """Return the injected result, or raise the injected error."""
        del image
        self.calls += 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class StubTranscriber:
    """Transcriber that returns an injected result (or error) and counts its calls."""

    def __init__(self, result: Transcript | Exception) -> None:
        """Remember what transcribe() should do."""
        self._result = result
        self.calls = 0

    def transcribe(self, samples: np.ndarray) -> Transcript:
        """Return the injected result, or raise the injected error."""
        del samples
        self.calls += 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class StubDetectorRegistry(DetectorRegistry):
    """Detector registry that returns stubs without loading any model."""

    def __init__(
        self,
        detector: Detector | Mapping[str, Detector],
        catalog: CategoryCatalog | None = None,
    ) -> None:
        """Store the stub detector(s) and an optional catalog."""
        self._detector = detector
        self._catalog = catalog

    def get(self, category_id: str) -> Detector:
        """Return the detector injected for this category."""
        if isinstance(self._detector, Mapping):
            return self._detector[category_id]
        del category_id
        return self._detector

    def category(self, category_id: str) -> CategoryConfig:
        """Return the config from the catalog, or a generic test config."""
        if self._catalog is not None:
            return self._catalog.get(category_id)
        return make_category_config(category_id)


class StubCategoryClassifier:
    """Classifier that returns injected similarities and records the calls."""

    def __init__(self, similarities: dict[str, float] | float) -> None:
        """Store one similarity per category id, or one for every id."""
        self._similarities = similarities
        self.calls: list[str] = []

    def similarity(self, image: Image.Image, category_id: str) -> float:
        """Return the injected similarity and record which category was scored."""
        del image
        self.calls.append(category_id)
        if isinstance(self._similarities, dict):
            return self._similarities[category_id]
        return self._similarities


def make_detection(score: float, flagged: int = 0, total: int = 100) -> Detection:
    """Build a detection whose mask flags `flagged` of `total` pixels."""
    mask = np.zeros(total, dtype=bool)
    mask[:flagged] = True
    return Detection(score=score, anomaly_map=mask.astype(np.float32), mask=mask)


TEST_SAMPLE_RATE = 16_000
TEST_TONE_HZ = 440
INT16_MAX = 32767


def make_wav(seconds: float = 1.0, amplitude: float = 0.5, rate: int = TEST_SAMPLE_RATE) -> bytes:
    """Build a mono WAV file holding a sine tone; amplitude 0 makes it silent."""
    times = np.arange(int(seconds * rate)) / rate
    tone = amplitude * np.sin(2 * np.pi * TEST_TONE_HZ * times)
    pcm = (tone * INT16_MAX).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        wav_file.writeframes(pcm.tobytes())
    return buffer.getvalue()


class StubReportWriter:
    """Report writer that returns queued drafts (or raises) without a model."""

    def __init__(
        self,
        *results: ReportDraft | Exception,
        source: ReportSource = ReportSource.AI,
    ) -> None:
        """Queue the results and record which source the stub represents."""
        self._results: Sequence[ReportDraft | Exception] = results or (
            AssertionError("StubReportWriter needs a result."),
        )
        self.source = source
        self.calls = 0
        self.facts: list[ReportFacts] = []
        self.transcripts: list[str | None] = []

    def write(
        self, facts: ReportFacts, image: Image.Image | None, transcript: str | None
    ) -> ReportDraft:
        """Return the next queued draft, or raise the next queued error."""
        del image
        index = min(self.calls, len(self._results) - 1)
        self.calls += 1
        self.facts.append(facts)
        self.transcripts.append(transcript)
        result = self._results[index]
        if isinstance(result, Exception):
            raise result
        return result


def make_draft(
    summary: str = "A defect was found during inspection.",
    findings: list[str] | None = None,
    recommendations: list[str] | None = None,
    defect_type: str | None = None,
    voice_note_conflict: str | None = None,
) -> ReportDraft:
    """Build a draft with grounded, deterministic wording."""
    return ReportDraft(
        summary=summary,
        findings=findings if findings is not None else ["The item needs attention."],
        recommendations=(
            recommendations
            if recommendations is not None
            else ["Reject the item and remove it from the batch."]
        ),
        defect_type=defect_type,
        voice_note_conflict=voice_note_conflict,
    )
