"""Tests for voice note validation and decoding."""

import io

import av
import numpy as np
import pytest

from app.core.audio import (
    SAMPLE_RATE,
    AudioTooLargeError,
    DecodedAudio,
    InvalidAudioError,
    is_silent,
    load_audio,
    sniff_format,
)
from tests.fakes import make_wav

MAX_BYTES = 1024 * 1024
MAX_SECONDS = 2.0
OPUS_RATE = 48_000
SECOND_TOLERANCE = 0.05


def load(data: bytes) -> DecodedAudio:
    """Call load_audio with the limits used by these tests."""
    return load_audio(data, max_bytes=MAX_BYTES, max_seconds=MAX_SECONDS)


def make_webm_opus(seconds: float = 1.0) -> bytes:
    """Encode a tone like a browser recording: WebM with Opus audio."""
    times = np.arange(int(seconds * OPUS_RATE)) / OPUS_RATE
    pcm = (0.5 * np.sin(2 * np.pi * 440 * times) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with av.open(buffer, mode="w", format="webm") as container:
        stream = container.add_stream("libopus", rate=OPUS_RATE, layout="mono")
        frame = av.AudioFrame.from_ndarray(pcm.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = OPUS_RATE
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    return buffer.getvalue()


def test_wav_is_decoded_to_16k_mono_floats() -> None:
    """A WAV is decoded to float samples with the right duration."""
    audio = load(make_wav(1.0))
    assert audio.samples.dtype == np.float32
    assert audio.duration_seconds == pytest.approx(1.0, abs=SECOND_TOLERANCE)
    assert not is_silent(audio.samples)


def test_other_sample_rates_are_resampled() -> None:
    """A 44.1 kHz file still ends up at 16 kHz."""
    audio = load(make_wav(1.0, rate=44_100))
    assert audio.samples.size == pytest.approx(SAMPLE_RATE, rel=0.02)


def test_browser_recording_format_is_accepted() -> None:
    """WebM with Opus, what MediaRecorder produces, decodes even without a duration header."""
    audio = load(make_webm_opus(1.0))
    assert audio.duration_seconds == pytest.approx(1.0, abs=SECOND_TOLERANCE)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", "wav"),
        (b"OggS\x00\x02", "ogg"),
        (b"\x1a\x45\xdf\xa3\x01", "webm"),
        (b"\x00\x00\x00\x18ftypM4A ", "mp4"),
        (b"ID3\x04\x00", "mp3"),
        (b"\xff\xfb\x90\x00", "mp3"),
        (b"RIFF\x00\x00\x00\x00AVI ", None),
        (b"plain text", None),
        (b"", None),
    ],
)
def test_format_is_read_from_the_bytes(data: bytes, expected: str | None) -> None:
    """The container is recognised from its first bytes, not from any name."""
    assert sniff_format(data) == expected


def test_empty_voice_note_is_rejected() -> None:
    """Zero bytes are an error."""
    with pytest.raises(InvalidAudioError, match="empty"):
        load(b"")


def test_unsupported_format_is_rejected() -> None:
    """Text sent as audio is refused before any decoding."""
    with pytest.raises(InvalidAudioError, match="Unsupported"):
        load(b"this is not audio at all")


@pytest.mark.parametrize(
    "data",
    [
        b"RIFF\x00\x00\x00\x00WAVEgarbage garbage garbage",
        make_wav()[:30],
        b"OggS" + b"\x00" * 50,
    ],
)
def test_corrupt_audio_is_rejected(data: bytes) -> None:
    """Files that look like audio but cannot be decoded are refused."""
    with pytest.raises(InvalidAudioError, match="not a valid audio"):
        load(data)


def test_oversized_voice_note_is_rejected() -> None:
    """Bytes over the limit are refused before decoding."""
    with pytest.raises(AudioTooLargeError):
        load_audio(make_wav(), max_bytes=100, max_seconds=MAX_SECONDS)


def test_too_long_voice_note_is_rejected() -> None:
    """Decoding stops as soon as the duration limit is passed."""
    with pytest.raises(AudioTooLargeError):
        load(make_wav(MAX_SECONDS + 1))


def test_silence_is_detected() -> None:
    """A decoded but silent recording is flagged as silent."""
    assert is_silent(load(make_wav(1.0, amplitude=0.0)).samples)


def test_empty_samples_count_as_silent() -> None:
    """No samples at all is treated as silence."""
    assert is_silent(np.zeros(0, dtype=np.float32))
