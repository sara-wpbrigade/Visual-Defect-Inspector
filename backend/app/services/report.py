"""Generate, validate and ground the report attached to one inspection."""

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter

from PIL import Image
from pydantic import ValidationError

from app.core.persona import PersonaConfig
from app.core.transcript import sanitize_transcript
from app.models.report_writer import ReportWriter, ReportWriterError
from app.schemas import (
    InspectionOutcome,
    InspectionReport,
    ReportContent,
    ReportDraft,
    ReportSource,
    Verdict,
)
from app.services.report_facts import ReportFacts, build_report_facts

logger = logging.getLogger(__name__)

MANUAL_REVIEW_NOTICE = "This result is uncertain and needs manual review before a final decision."
UNKNOWN_DEFECT_TYPE = "unknown"
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
GROUNDING_ERROR = "The report contains numbers that are not in the facts or the transcript."
SCHEMA_ERROR = "The report draft does not match the required schema."


class ReportValidationError(ValueError):
    """Raised when a draft breaks the schema, the persona or the grounding rules."""


def utc_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


class ReportService:
    """Word the facts with the configured writer and a deterministic fallback."""

    def __init__(
        self,
        writer: ReportWriter,
        fallback_writer: ReportWriter,
        persona: PersonaConfig,
        max_attempts: int,
        max_transcript_chars: int,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        """Store the injected writers, persona, limits and clock."""
        self._writer = writer
        self._fallback_writer = fallback_writer
        self._persona = persona
        self._max_attempts = max_attempts
        self._max_transcript_chars = max_transcript_chars
        self._clock = clock

    def generate(
        self,
        inspection_id: str,
        outcome: InspectionOutcome,
        image: Image.Image,
        transcript: str | None = None,
    ) -> InspectionReport:
        """Return a validated report; never let a writer failure fail the inspection."""
        started = perf_counter()
        facts = build_report_facts(outcome, self._persona)
        clean_transcript = self._clean_transcript(transcript)
        content, source = self._from_writer(facts, image, clean_transcript)
        report = self._build_report(inspection_id, facts, content, source)
        logger.info(
            "Report generated source=%s duration_ms=%.1f",
            source,
            (perf_counter() - started) * 1000,
        )
        return report

    def _from_writer(
        self, facts: ReportFacts, image: Image.Image, transcript: str | None
    ) -> tuple[ReportContent, ReportSource]:
        """Try the configured writer, then fall back to the template."""
        attempts = 1 if self._writer.source is ReportSource.TEMPLATE else self._max_attempts
        for attempt in range(1, attempts + 1):
            try:
                draft = self._writer.write(facts, image, transcript)
                content = validate_draft(draft, facts, self._persona, transcript)
                return content, self._writer.source
            except (ReportWriterError, ReportValidationError) as exc:
                logger.warning("Report attempt %d failed with %s", attempt, type(exc).__name__)
        return self._from_fallback(facts, image, transcript)

    def _from_fallback(
        self, facts: ReportFacts, image: Image.Image, transcript: str | None
    ) -> tuple[ReportContent, ReportSource]:
        """Validate the deterministic template draft."""
        draft = self._fallback_writer.write(facts, image, transcript)
        return validate_draft(draft, facts, self._persona, transcript), ReportSource.TEMPLATE

    def _clean_transcript(self, transcript: str | None) -> str | None:
        """Sanitize and cap the transcript, treating an empty result as absent."""
        if transcript is None:
            return None
        clean = sanitize_transcript(transcript, self._max_transcript_chars)
        return clean.text or None

    def _build_report(
        self,
        inspection_id: str,
        facts: ReportFacts,
        content: ReportContent,
        source: ReportSource,
    ) -> InspectionReport:
        """Assemble the report fields that code controls."""
        return InspectionReport(
            report_id=inspection_id,
            generated_at=self._clock(),
            persona=self._persona.name,
            source=source,
            content=content,
            manual_review_notice=MANUAL_REVIEW_NOTICE if facts.needs_review else None,
        )


def validate_draft(
    draft: ReportDraft,
    facts: ReportFacts,
    persona: PersonaConfig,
    transcript: str | None,
) -> ReportContent:
    """Apply the strict schema, defect-type rules and grounding check to a draft."""
    try:
        content = ReportContent.model_validate(draft.model_dump())
    except ValidationError as exc:
        raise ReportValidationError(SCHEMA_ERROR) from exc
    defect_type = _normalize_defect_type(content.defect_type, facts, persona)
    content = content.model_copy(update={"defect_type": defect_type})
    _check_grounding(content, facts, transcript)
    return content


def _normalize_defect_type(
    defect_type: str | None, facts: ReportFacts, persona: PersonaConfig
) -> str | None:
    """Return a canonical allowed defect type, or None for a pass or an unnamed defect."""
    normalized = (defect_type or "").strip().lower()
    if facts.verdict is Verdict.PASS:
        if normalized:
            raise ReportValidationError("A passing item cannot have a defect type.")
        return None
    if not normalized:
        return None
    allowed = {value.lower() for value in persona.defect_types}
    if normalized in allowed or normalized == UNKNOWN_DEFECT_TYPE:
        return normalized
    raise ReportValidationError("The defect type is not allowed for this persona.")


def _check_grounding(content: ReportContent, facts: ReportFacts, transcript: str | None) -> None:
    """Reject any number that is not present in the facts or the transcript."""
    allowed_source = facts.model_dump_json() + "\n" + (transcript or "")
    allowed_numbers = set(NUMBER_PATTERN.findall(allowed_source))
    texts = [content.summary, *content.findings, *content.recommendations]
    if content.voice_note_conflict:
        texts.append(content.voice_note_conflict)
    used_numbers = {number for text in texts for number in NUMBER_PATTERN.findall(text)}
    if used_numbers - allowed_numbers:
        raise ReportValidationError(GROUNDING_ERROR)
