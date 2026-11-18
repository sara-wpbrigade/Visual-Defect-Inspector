"""Test doubles and fixed data shared by the test suite."""

from collections.abc import Sequence

import numpy as np
from PIL import Image

from app.models.detector import Detection
from app.schemas import ReportDraft, ReportSource
from app.services.report_facts import ReportFacts

PERSONA_DATA = {
    "name": "test_persona",
    "defect_types": ["scratch"],
    "decision_cutoff": 0.5,
    "review_margin": 0.1,
    "severity_bands": {"low_max": 0.01, "medium_max": 0.05},
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


class StubDetector:
    """Detector that returns an injected result (or error) without a model."""

    def __init__(self, result: Detection | Exception) -> None:
        """Remember what detect() should do."""
        self._result = result

    def detect(self, image: Image.Image) -> Detection:
        """Return the injected result, or raise the injected error."""
        del image
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def make_detection(score: float, flagged: int = 0, total: int = 100) -> Detection:
    """Build a detection whose mask flags `flagged` of `total` pixels."""
    mask = np.zeros(total, dtype=bool)
    mask[:flagged] = True
    return Detection(score=score, anomaly_map=mask.astype(np.float32), mask=mask)


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
