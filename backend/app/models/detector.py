"""The detector interface: what the service layer needs from an AI model."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Detection:
    """The raw output of one anomaly detection run."""

    score: float
    anomaly_map: np.ndarray
    mask: np.ndarray


class Detector(Protocol):
    """An anomaly detector: one photo in, one score and location map out."""

    def detect(self, image: Image.Image) -> Detection:
        """Return the anomaly score, heatmap and flagged-pixel mask."""
        ...
