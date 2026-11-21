"""The optional voice note attached to one inspection."""

from enum import StrEnum

from pydantic import BaseModel, Field


class VoiceStatus(StrEnum):
    """Whether a voice note produced usable text."""

    TRANSCRIBED = "transcribed"
    NO_SPEECH = "no_speech"


class VoiceNoteResult(BaseModel):
    """The cleaned transcript of an optional voice note."""

    status: VoiceStatus
    text: str
    language: str | None = None
    duration_seconds: float = Field(ge=0)
    truncated: bool = False
