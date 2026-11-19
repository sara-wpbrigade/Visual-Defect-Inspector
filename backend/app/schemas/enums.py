"""Enumerations shared across the inspection domain."""

from enum import StrEnum


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
