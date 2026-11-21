"""The transcriber interface: what the service layer needs from a speech model."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class Transcript:
    """The raw output of one transcription run."""

    text: str
    language: str | None


class Transcriber(Protocol):
    """A speech-to-text model: 16 kHz mono samples in, text out."""

    def transcribe(self, samples: np.ndarray) -> Transcript:
        """Return the spoken text and the detected language."""
        ...
