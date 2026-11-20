"""The inspection use case: one photo in, the assessed facts out."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PIL import Image

from app.core.persona import PersonaConfig
from app.models.detector import Detection, Detector
from app.models.registry import DetectorRegistry
from app.schemas import InspectionOutcome
from app.services import rules

logger = logging.getLogger(__name__)


class DetectionError(RuntimeError):
    """Raised when the detector cannot produce a result for an image."""


@dataclass(frozen=True)
class InspectionAnalysis:
    """The assessed facts, the raw detection and the effective persona."""

    outcome: InspectionOutcome
    detection: Detection
    persona: PersonaConfig


class InspectionService:
    """Run one photo through its category's detector and effective persona."""

    def __init__(self, registry: DetectorRegistry, base_persona: PersonaConfig) -> None:
        """Store the detector registry and the persona to overlay per category."""
        self._registry = registry
        self._base_persona = base_persona

    def inspect(self, image: Image.Image, category_id: str) -> InspectionAnalysis:
        """Detect and assess *image* with the detector and persona of *category_id*."""
        config = self._registry.category(category_id)
        persona = self._base_persona.for_category(config)
        detection = self._detect(self._registry.get(category_id), image)
        assessment = rules.assess(detection.score, detection.mask, persona)
        logger.info(
            "Inspection finished: cat=%s verdict=%s severity=%s action=%s review=%s",
            category_id,
            assessment.verdict,
            assessment.severity,
            assessment.action,
            assessment.needs_review,
        )
        outcome = InspectionOutcome(score=detection.score, assessment=assessment)
        return InspectionAnalysis(outcome=outcome, detection=detection, persona=persona)

    @staticmethod
    def _detect(detector: Detector, image: Image.Image) -> Detection:
        """Run the detector, turning any model failure into a domain error."""
        try:
            return detector.detect(image)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("The detector failed")
            raise DetectionError("The detector could not analyse the image.") from exc
