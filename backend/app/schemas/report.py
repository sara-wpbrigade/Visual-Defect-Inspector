"""Report drafts and the validated report attached to an inspection."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from .enums import ReportSource

MAX_SUMMARY_CHARS = 400
MAX_FINDINGS = 5
MAX_RECOMMENDATIONS = 4
MAX_FINDING_CHARS = 240
MAX_RECOMMENDATION_CHARS = 240
MAX_DEFECT_TYPE_CHARS = 60
MAX_CONFLICT_CHARS = 400

Finding = Annotated[str, Field(max_length=MAX_FINDING_CHARS)]
Recommendation = Annotated[str, Field(max_length=MAX_RECOMMENDATION_CHARS)]


class ReportDraft(BaseModel):
    """The unconstrained JSON shape the model must return."""

    summary: str
    findings: list[str]
    recommendations: list[str]
    defect_type: str | None
    voice_note_conflict: str | None


class ReportContent(BaseModel):
    """Report text after the strict schema and grounding checks."""

    summary: Annotated[str, Field(min_length=1, max_length=MAX_SUMMARY_CHARS)]
    findings: Annotated[list[Finding], Field(min_length=1, max_length=MAX_FINDINGS)]
    recommendations: Annotated[
        list[Recommendation], Field(min_length=1, max_length=MAX_RECOMMENDATIONS)
    ]
    defect_type: Annotated[str, Field(max_length=MAX_DEFECT_TYPE_CHARS)] | None
    voice_note_conflict: Annotated[str, Field(max_length=MAX_CONFLICT_CHARS)] | None


class InspectionReport(BaseModel):
    """The validated report attached to one inspection."""

    report_id: str = Field(min_length=1)
    generated_at: datetime
    persona: str = Field(min_length=1)
    source: ReportSource
    content: ReportContent
    manual_review_notice: str | None = None
