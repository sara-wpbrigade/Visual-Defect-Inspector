"""The report writer interface: what the service layer needs from an LLM."""

from typing import Protocol

from PIL import Image

from app.schemas import ReportDraft, ReportSource
from app.services.report_facts import ReportFacts


class ReportWriterError(RuntimeError):
    """Raised when a report writer cannot produce a draft."""


class ReportWriter(Protocol):
    """Turn authoritative facts into report wording."""

    source: ReportSource

    def write(
        self, facts: ReportFacts, image: Image.Image | None, transcript: str | None
    ) -> ReportDraft:
        """Return a draft; the caller validates it before use."""
        ...
