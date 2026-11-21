"""Tests for pure batch decision and summary logic."""

from datetime import UTC, datetime

from app.core.persona import BatchPolicy
from app.schemas import (
    Action,
    Assessment,
    InspectionReport,
    ReportContent,
    ReportSource,
    Severity,
    Verdict,
)
from app.services.batch import BatchDecision, decide_batch, summarize_batch
from app.services.repository import InspectionRecord

CREATED_AT = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)


def make_item(
    verdict: Verdict = Verdict.PASS,
    severity: Severity = Severity.NONE,
    needs_review: bool = False,
    category: str = "bottle",
) -> InspectionRecord:
    """Create a minimal inspection record for batch testing."""
    assessment = Assessment(
        verdict=verdict,
        confidence=0.95,
        needs_review=needs_review,
        severity=severity,
        area_ratio=0.05 if verdict is Verdict.DEFECT else 0.0,
        action=Action.REJECT if verdict is Verdict.DEFECT else Action.ACCEPT,
        location=None,
    )
    content = ReportContent(
        summary="Summary",
        findings=["Finding"],
        recommendations=["Recommendation"],
        defect_type=None,
        voice_note_conflict=None,
    )
    report = InspectionReport(
        report_id="1" * 32,
        generated_at=CREATED_AT,
        persona="factory_qc_operator",
        source=ReportSource.TEMPLATE,
        content=content,
        manual_review_notice=None,
    )
    return InspectionRecord(
        id="1" * 32,
        created_at=CREATED_AT,
        persona="factory_qc_operator",
        batch_id="batch-test",
        category=category,
        score=0.9 if verdict is Verdict.DEFECT else 0.1,
        assessment=assessment,
        report=report,
    )


def test_batch_all_pass_is_passed() -> None:
    """A batch where all items pass is PASSED."""
    policy = BatchPolicy(reject_min_severity=Severity.LOW)
    items = [make_item(), make_item()]
    assert decide_batch(items, policy) is BatchDecision.PASSED


def test_batch_defect_exceeding_severity_is_rejected() -> None:
    """A clear defect exceeding min severity rejects the batch."""
    policy = BatchPolicy(reject_min_severity=Severity.LOW)
    items = [make_item(), make_item(Verdict.DEFECT, Severity.MEDIUM, False)]
    assert decide_batch(items, policy) is BatchDecision.REJECTED


def test_batch_defect_below_severity_does_not_reject() -> None:
    """A low severity defect when policy requires HIGH does not reject."""
    policy = BatchPolicy(reject_min_severity=Severity.HIGH)
    items = [make_item(), make_item(Verdict.DEFECT, Severity.LOW, False)]
    assert decide_batch(items, policy) is BatchDecision.PASSED


def test_batch_needs_review_item_causes_needs_review() -> None:
    """Any item needing review flags the entire batch as NEEDS_REVIEW."""
    policy = BatchPolicy(reject_min_severity=Severity.LOW)
    items = [make_item(), make_item(Verdict.PASS, Severity.NONE, True)]
    assert decide_batch(items, policy) is BatchDecision.NEEDS_REVIEW


def test_summarize_batch_aggregates_counts() -> None:
    """Batch summary calculates counts and categories accurately."""
    policy = BatchPolicy(reject_min_severity=Severity.LOW)
    items = [
        make_item(Verdict.PASS, category="bottle"),
        make_item(Verdict.DEFECT, Severity.HIGH, False, category="metal_nut"),
        make_item(Verdict.PASS, needs_review=True, category="bottle"),
    ]
    summary = summarize_batch("batch-abc", items, policy)
    assert summary.batch_id == "batch-abc"
    assert summary.decision is BatchDecision.REJECTED
    assert summary.item_count == 3
    assert summary.defect_count == 1
    assert summary.pass_count == 2
    assert summary.review_count == 1
    assert summary.categories == ["bottle", "metal_nut"]
