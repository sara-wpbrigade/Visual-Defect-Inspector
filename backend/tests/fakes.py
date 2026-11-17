"""Test doubles and fixed data shared by the test suite."""

import numpy as np
from PIL import Image

from app.models.detector import Detection

PERSONA_DATA = {
    "name": "test_persona",
    "defect_types": ["scratch"],
    "decision_cutoff": 0.5,
    "review_margin": 0.1,
    "severity_bands": {"low_max": 0.01, "medium_max": 0.05},
    "on_pass": "accept",
    "on_uncertain": "re_inspect",
    "on_defect": {"low": "rework", "medium": "rework", "high": "reject"},
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
