"""Shared types: the vocabulary of an inspection result."""

from .assessment import Assessment, DefectLocation, InspectionOutcome
from .enums import DEFECT_SEVERITIES, Action, ReportSource, Severity, Verdict
from .inspection import (
    BATCH_ID_PATTERN,
    ImageUrls,
    InspectionCreated,
    InspectionResult,
)
from .report import (
    MAX_CONFLICT_CHARS,
    MAX_DEFECT_TYPE_CHARS,
    MAX_FINDING_CHARS,
    MAX_FINDINGS,
    MAX_RECOMMENDATION_CHARS,
    MAX_RECOMMENDATIONS,
    MAX_SUMMARY_CHARS,
    Finding,
    InspectionReport,
    Recommendation,
    ReportContent,
    ReportDraft,
)

__all__ = [
    "Action",
    "Assessment",
    "BATCH_ID_PATTERN",
    "DEFECT_SEVERITIES",
    "DefectLocation",
    "Finding",
    "ImageUrls",
    "InspectionCreated",
    "InspectionOutcome",
    "InspectionReport",
    "InspectionResult",
    "MAX_CONFLICT_CHARS",
    "MAX_DEFECT_TYPE_CHARS",
    "MAX_FINDING_CHARS",
    "MAX_FINDINGS",
    "MAX_RECOMMENDATION_CHARS",
    "MAX_RECOMMENDATIONS",
    "MAX_SUMMARY_CHARS",
    "Recommendation",
    "ReportContent",
    "ReportDraft",
    "ReportSource",
    "Severity",
    "Verdict",
]
