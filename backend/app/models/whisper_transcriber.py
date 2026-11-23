"""faster-whisper transcriber: a local speech model loaded once per process."""

import logging
import threading

import numpy as np
from faster_whisper import WhisperModel

from app.models.transcriber import Transcript

logger = logging.getLogger(__name__)


class FasterWhisperTranscriber:
    """Transcriber implementation backed by a local faster-whisper model."""

    def __init__(self, model_size: str, device: str, compute_type: str) -> None:
        """Load the model, downloading it on first use."""
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self._lock = threading.Lock()
        logger.info("Loaded faster-whisper %s on %s (%s)", model_size, device, compute_type)

    def transcribe(self, samples: np.ndarray) -> Transcript:
        """Transcribe samples, letting voice activity detection skip silence."""
        # The local speech model and its device are shared, so one clip is
        # transcribed at a time; the segment generator is drained inside the lock.
        with self._lock:
            segments, info = self._model.transcribe(samples, vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments).strip()
            return Transcript(text=text, language=info.language)
