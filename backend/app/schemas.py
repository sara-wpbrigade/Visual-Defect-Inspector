"""Shared types: the vocabulary of an inspection result."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

MAX_SUMMARY_CHARS = 400
MAX_FINDINGS = 5
MAX_RECOMMENDATIONS = 4
MAX_FINDING_CHARS = 240
MAX_RECOMMENDATION_CHARS = 240
MAX_DEFECT_TYPE_CHARS = 60
MAX_CONFLICT_CHARS = 400
BATCH_ID_PATTERN = r"^[A-Za-z0-9_-]{1,40}$"

Finding = Annotated[str, Field(max_length=MAX_FINDING_CHARS)]
Recommendation = Annotated[str, Field(max_length=MAX_RECOMMENDATION_CHARS)]


class Verdict(StrEnum):
    """Whether the inspected item passed."""

    PASS = "pass"
    DEFECT = "defect"


class Severity(StrEnum):
    """How serious a defect is."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Action(StrEnum):
    """What the operator should do next."""

    ACCEPT = "accept"
    REWORK = "rework"
    REJECT = "reject"
    RE_INSPECT = "re_inspect"


class ReportSource(StrEnum):
    """Where the wording of a report came from."""

    AI = "ai"
    TEMPLATE = "template"


DEFECT_SEVERITIES = (Severity.LOW, Severity.MEDIUM, Severity.HIGH)


class DefectLocation(BaseModel):
    """Where the flagged pixels are, as a grid cell and a normalized box."""

    region: str = Field(min_length=1)
    bbox: tuple[float, float, float, float]

    @field_validator("bbox")
    @classmethod
    def check_bbox_bounds(
        cls, value: tuple[float, float, float, float]
    ) -> tuple[float, float, float, float]:
        """Require every normalized coordinate to be inside the image."""
        if any(coordinate < 0 or coordinate > 1 for coordinate in value):
            raise ValueError("bbox coordinates must be between 0 and 1")
        return value


class Assessment(BaseModel):
    """The facts decided by the rules, before any LLM wording."""

    verdict: Verdict
    confidence: float = Field(ge=0, le=1)
    needs_review: bool
    severity: Severity
    area_ratio: float = Field(ge=0, le=1)
    action: Action
    location: DefectLocation | None = None


class InspectionOutcome(BaseModel):
    """The detector score plus the rules assessment, before storage."""

    score: float = Field(ge=0)
    assessment: Assessment


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


class InspectionResult(InspectionOutcome):
    """One finished inspection as returned by the API."""

    inspection_id: str = Field(min_length=1)
    report: InspectionReport


class ImageUrls(BaseModel):
    """Relative URLs of the three stored images for one inspection."""

    photo: str
    overlay: str
    thumbnail: str


class InspectionCreated(InspectionResult):
    """One finished inspection, including where its images are stored."""

    created_at: datetime
    batch_id: str | None = None
    images: ImageUrls
