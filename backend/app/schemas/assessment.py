"""The facts decided for one inspected item."""

from pydantic import BaseModel, Field, field_validator

from .enums import Action, Severity, Verdict


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
