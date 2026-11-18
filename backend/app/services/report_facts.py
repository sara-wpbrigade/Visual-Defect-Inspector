"""The factual inputs a report writer is allowed to word."""

from pydantic import BaseModel, Field

from app.core.persona import PersonaConfig
from app.schemas import Action, InspectionOutcome, Severity, Verdict

PERCENT_FACTOR = 100
PERCENT_DIGITS = 1
SCORE_DIGITS = 3


class ReportFacts(BaseModel):
    """Everything the report writer may use, including preformatted numbers."""

    persona: str
    audience: str
    tone: str
    language: str
    verdict: Verdict
    severity: Severity
    action: Action
    action_text: str
    needs_review: bool
    region: str | None
    allowed_defect_types: list[str] = Field(min_length=1)
    confidence_percent: str
    flagged_area_percent: str
    anomaly_score: str


def build_report_facts(outcome: InspectionOutcome, persona: PersonaConfig) -> ReportFacts:
    """Build the writer inputs from the assessment, never from model text."""
    assessment = outcome.assessment
    location = assessment.location
    return ReportFacts(
        persona=persona.name,
        audience=persona.report.audience,
        tone=persona.report.tone,
        language=persona.report.language,
        verdict=assessment.verdict,
        severity=assessment.severity,
        action=assessment.action,
        action_text=persona.action_text[assessment.action],
        needs_review=assessment.needs_review,
        region=location.region if location is not None else None,
        allowed_defect_types=list(persona.defect_types),
        confidence_percent=_format_percent(assessment.confidence),
        flagged_area_percent=_format_percent(assessment.area_ratio),
        anomaly_score=f"{outcome.score:.{SCORE_DIGITS}f}",
    )


def _format_percent(ratio: float) -> str:
    """Format a 0..1 ratio with one decimal, for example 0.9369 -> 93.7%."""
    return f"{ratio * PERCENT_FACTOR:.{PERCENT_DIGITS}f}%"
