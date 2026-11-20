"""Tests for the inspection service with a stubbed detector."""

from collections.abc import Callable

import pytest
from PIL import Image

from app.models.detector import Detection
from app.schemas import Action, Severity, Verdict
from app.services.inspection import DetectionError, InspectionService
from tests.fakes import CATEGORY_ID

IMAGE = Image.new("RGB", (8, 8))

DetectionFactory = Callable[..., Detection]
ServiceFactory = Callable[..., InspectionService]


def test_good_item_passes_and_is_accepted(
    service_factory: ServiceFactory, detection_factory: DetectionFactory
) -> None:
    """A low score with nothing flagged passes with no severity."""
    outcome = service_factory(detection_factory(0.2)).inspect(IMAGE, CATEGORY_ID).outcome
    assert (outcome.assessment.verdict, outcome.assessment.severity) == (
        Verdict.PASS,
        Severity.NONE,
    )
    assert outcome.assessment.action is Action.ACCEPT
    assert outcome.score == 0.2


def test_large_defect_is_high_severity_and_rejected(
    service_factory: ServiceFactory, detection_factory: DetectionFactory
) -> None:
    """A high score with a large flagged area is rejected."""
    outcome = service_factory(detection_factory(0.9, 30)).inspect(IMAGE, CATEGORY_ID).outcome
    assert (outcome.assessment.severity, outcome.assessment.action) == (
        Severity.HIGH,
        Action.REJECT,
    )
    assert outcome.assessment.needs_review is False


def test_borderline_score_needs_review(
    service_factory: ServiceFactory, detection_factory: DetectionFactory
) -> None:
    """A score near the cutoff is flagged for re-inspection."""
    outcome = service_factory(detection_factory(0.55, 3)).inspect(IMAGE, CATEGORY_ID).outcome
    assert outcome.assessment.needs_review is True
    assert outcome.assessment.action is Action.RE_INSPECT


def test_detector_failure_becomes_a_domain_error(
    service_factory: ServiceFactory,
) -> None:
    """A model crash is reported as a DetectionError, not swallowed."""
    with pytest.raises(DetectionError, match="could not analyse"):
        service_factory(RuntimeError("model exploded")).inspect(IMAGE, CATEGORY_ID)
