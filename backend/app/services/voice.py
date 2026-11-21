"""The voice note use case: decoded audio in, a cleaned transcript out."""

import logging
from collections.abc import Callable

import numpy as np

from app.core.audio import DecodedAudio, is_silent
from app.core.transcript import sanitize_transcript
from app.models.transcriber import Transcriber, Transcript
from app.schemas import VoiceNoteResult, VoiceStatus

logger = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    """Raised when the speech model cannot transcribe a voice note."""


class VoiceNoteService:
    """Turn a decoded voice note into a safe, length-capped transcript."""

    def __init__(self, transcriber_provider: Callable[[], Transcriber], max_chars: int) -> None:
        """Store how to get the model (loaded on first use) and the transcript cap."""
        self._provider = transcriber_provider
        self._max_chars = max_chars

    def process(self, audio: DecodedAudio) -> VoiceNoteResult:
        """Return the cleaned transcript, or a no-speech result for silent audio."""
        if is_silent(audio.samples):
            return self._no_speech(audio)
        transcript = self._transcribe(audio.samples)
        clean = sanitize_transcript(transcript.text, self._max_chars)
        if not clean.text:
            return self._no_speech(audio)
        # Only sizes are logged: a transcript can contain personal data.
        logger.info(
            "Voice note transcribed: %.1f s, %d characters, truncated=%s",
            audio.duration_seconds,
            len(clean.text),
            clean.truncated,
        )
        return VoiceNoteResult(
            status=VoiceStatus.TRANSCRIBED,
            text=clean.text,
            language=transcript.language,
            duration_seconds=audio.duration_seconds,
            truncated=clean.truncated,
        )

    def _transcribe(self, samples: np.ndarray) -> Transcript:
        """Run the speech model, turning any failure into a domain error."""
        try:
            return self._provider().transcribe(samples)
        except Exception as exc:
            logger.exception("The transcriber failed")
            raise TranscriptionError("The voice note could not be transcribed.") from exc

    @staticmethod
    def _no_speech(audio: DecodedAudio) -> VoiceNoteResult:
        """Build the result for a voice note without intelligible speech."""
        return VoiceNoteResult(
            status=VoiceStatus.NO_SPEECH, text="", duration_seconds=audio.duration_seconds
        )
