"""Validation and decoding of uploaded voice notes."""

import io
from dataclasses import dataclass

import av
import numpy as np
from av.error import FFmpegError

SAMPLE_RATE = 16_000
INT16_SCALE = 32768.0
SILENCE_RMS_THRESHOLD = 0.005
UNSUPPORTED_AUDIO_MESSAGE = "Unsupported audio format; use WAV, MP3, OGG, WebM or M4A."
INVALID_AUDIO_MESSAGE = "The voice note is not a valid audio file."

RIFF_MAGIC = b"RIFF"
WAVE_MAGIC = b"WAVE"
ID3_MAGIC = b"ID3"
OGG_MAGIC = b"OggS"
WEBM_MAGIC = b"\x1a\x45\xdf\xa3"
MP4_BRAND_MARKER = b"ftyp"
MP3_SYNC_BYTE = 0xFF
MP3_SYNC_MASK = 0xE0


class InvalidAudioError(ValueError):
    """Raised when a voice note is not usable audio."""


class AudioTooLargeError(InvalidAudioError):
    """Raised when a voice note exceeds the byte or duration limits."""


@dataclass(frozen=True)
class DecodedAudio:
    """A voice note decoded to 16 kHz mono float samples."""

    samples: np.ndarray
    duration_seconds: float


def load_audio(data: bytes, *, max_bytes: int, max_seconds: float) -> DecodedAudio:
    """Validate raw voice-note bytes and decode them to 16 kHz mono samples.

    The real container format is read from the file contents, never from the
    client's filename or content type.

    Raises:
        InvalidAudioError: The bytes are empty, corrupt or an unsupported format.
        AudioTooLargeError: The bytes or the decoded duration are over the limit.
    """
    if not data:
        raise InvalidAudioError("The voice note is empty.")
    if len(data) > max_bytes:
        raise AudioTooLargeError(f"Voice notes must be at most {max_bytes} bytes.")
    if sniff_format(data) is None:
        raise InvalidAudioError(UNSUPPORTED_AUDIO_MESSAGE)
    samples = _decode(data, max_seconds)
    return DecodedAudio(samples=samples, duration_seconds=samples.size / SAMPLE_RATE)


def sniff_format(data: bytes) -> str | None:
    """Return the audio container named by the first bytes of a file, or None."""
    if data[:4] == RIFF_MAGIC and data[8:12] == WAVE_MAGIC:
        return "wav"
    if data[:4] == OGG_MAGIC:
        return "ogg"
    if data[:4] == WEBM_MAGIC:
        return "webm"
    if data[4:8] == MP4_BRAND_MARKER:
        return "mp4"
    if data[:3] == ID3_MAGIC or _is_mp3_frame(data):
        return "mp3"
    return None


def is_silent(samples: np.ndarray) -> bool:
    """Return True when there is no audio or it is too quiet to hold speech."""
    if samples.size == 0:
        return True
    rms = float(np.sqrt(np.mean(np.square(samples))))
    return rms < SILENCE_RMS_THRESHOLD


def _is_mp3_frame(data: bytes) -> bool:
    """Return True when the bytes start with an MP3 frame sync."""
    return len(data) > 1 and data[0] == MP3_SYNC_BYTE and (data[1] & MP3_SYNC_MASK) == MP3_SYNC_MASK


def _decode(data: bytes, max_seconds: float) -> np.ndarray:
    """Decode to 16 kHz mono floats, stopping early if the duration limit is passed."""
    max_samples = int(max_seconds * SAMPLE_RATE)
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks: list[np.ndarray] = []
    total = 0
    try:
        with av.open(io.BytesIO(data), mode="r") as container:
            if not container.streams.audio:
                raise InvalidAudioError(INVALID_AUDIO_MESSAGE)
            for frame in container.decode(audio=0):
                for resampled in resampler.resample(frame):
                    chunk = resampled.to_ndarray().reshape(-1)
                    total += chunk.size
                    if total > max_samples:
                        raise AudioTooLargeError(f"Voice notes must be at most {max_seconds:g} s.")
                    chunks.append(chunk)
    except FFmpegError as exc:
        raise InvalidAudioError(INVALID_AUDIO_MESSAGE) from exc
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / INT16_SCALE
