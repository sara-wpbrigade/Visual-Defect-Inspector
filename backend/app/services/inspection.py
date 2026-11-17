"""The inspection use case: one photo in, the assessed facts out."""

import logging

from PIL import Image

from app.core.persona import PersonaConfig
from app.models.detector import Detection, Detector
from app.schemas import InspectionOutcome
from app.services import rules

logger = logging.getLogger(__name__)


class DetectionError(RuntimeError):
    """Raised when the detector cannot produce a result for an image."""


class InspectionService:
    """Run one photo through the detector and the persona rules."""

    def __init__(self, detector: Detector, persona: PersonaConfig) -> None:
        """Store the injected model and persona."""
        self._detector = detector
        self._persona = persona

    def inspect(self, image: Image.Image) -> InspectionOutcome:
        """Return the detector score and the assessed facts for one photo."""
        detection = self._detect(image)
        assessment = rules.assess(detection.score, detection.mask, self._persona)
        logger.info(
            "Inspection finished: verdict=%s severity=%s action=%s review=%s",
            assessment.verdict,
            assessment.severity,
            assessment.action,
            assessment.needs_review,
        )
        return InspectionOutcome(score=detection.score, assessment=assessment)

    def _detect(self, image: Image.Image) -> Detection:
        """Run the detector, turning any model failure into a domain error."""
        try:
            return self._detector.detect(image)
        except Exception as exc:
            logger.exception("The detector failed")
            raise DetectionError("The detector could not analyse the image.") from exc
