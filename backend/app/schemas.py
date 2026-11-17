"""Shared types: the vocabulary of an inspection result."""

from enum import StrEnum

from pydantic import BaseModel, Field


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


DEFECT_SEVERITIES = (Severity.LOW, Severity.MEDIUM, Severity.HIGH)


class Assessment(BaseModel):
    """The facts decided by the rules, before any LLM wording."""

    verdict: Verdict
    confidence: float = Field(ge=0, le=1)
    needs_review: bool
    severity: Severity
    area_ratio: float = Field(ge=0, le=1)
    action: Action
