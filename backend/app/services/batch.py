"""Batch decision logic and summary aggregation."""

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from app.core.persona import BatchPolicy
from app.schemas import Severity, Verdict
from app.services.repository import InspectionRecord

SEVERITY_ORDER = {
    Severity.NONE: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
}


class BatchDecision(StrEnum):
    """Aggregate quality verdict for a batch of inspected items."""

    PASSED = "Passed"
    REJECTED = "Rejected"
    NEEDS_REVIEW = "Needs review"


class BatchSummary(BaseModel):
    """Aggregated statistics and verdict for one batch."""

    batch_id: str
    decision: BatchDecision
    item_count: int
    defect_count: int
    pass_count: int
    review_count: int
    categories: list[str]
    last_inspection_at: datetime


def decide_batch(items: Sequence[InspectionRecord], policy: BatchPolicy) -> BatchDecision:
    """Compute the batch verdict from its items and the configured rejection policy."""
    min_rank = SEVERITY_ORDER[policy.reject_min_severity]
    for item in items:
        assessment = item.assessment
        is_defect = assessment.verdict is Verdict.DEFECT
        if (
            is_defect
            and not assessment.needs_review
            and SEVERITY_ORDER[assessment.severity] >= min_rank
        ):
            return BatchDecision.REJECTED

    if any(item.assessment.needs_review for item in items):
        return BatchDecision.NEEDS_REVIEW

    return BatchDecision.PASSED


def summarize_batch(
    batch_id: str, items: Sequence[InspectionRecord], policy: BatchPolicy
) -> BatchSummary:
    """Aggregate record attributes into a BatchSummary."""
    categories = sorted(list({item.category for item in items if item.category}))
    defect_count = sum(1 for item in items if item.assessment.verdict is Verdict.DEFECT)
    pass_count = sum(1 for item in items if item.assessment.verdict is Verdict.PASS)
    review_count = sum(1 for item in items if item.assessment.needs_review)
    last_inspection = max(item.created_at for item in items)
    return BatchSummary(
        batch_id=batch_id,
        decision=decide_batch(items, policy),
        item_count=len(items),
        defect_count=defect_count,
        pass_count=pass_count,
        review_count=review_count,
        categories=categories,
        last_inspection_at=last_inspection,
    )
