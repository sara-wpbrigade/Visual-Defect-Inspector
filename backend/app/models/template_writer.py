"""Deterministic report wording that needs no model or network."""

from PIL import Image

from app.schemas import ReportDraft, ReportSource, Verdict
from app.services.report_facts import ReportFacts


class TemplateReportWriter:
    """Build a plain, grounded draft from the facts and the persona action text."""

    source = ReportSource.TEMPLATE

    def write(
        self, facts: ReportFacts, image: Image.Image | None, transcript: str | None
    ) -> ReportDraft:
        """Return the same draft every time for the same facts."""
        del image, transcript
        return ReportDraft(
            summary=_summary(facts),
            findings=_findings(facts),
            recommendations=[facts.action_text],
            defect_type=None,
            voice_note_conflict=None,
        )


def _summary(facts: ReportFacts) -> str:
    """State the verdict, severity and region without adding new numbers."""
    if facts.verdict is Verdict.PASS:
        return (
            f"The item passed inspection with {facts.confidence_percent} confidence; "
            "no defect was found."
        )
    region = facts.region or "the inspected area"
    return (
        f"A {facts.severity} defect was found in {region} "
        f"with {facts.confidence_percent} confidence."
    )


def _findings(facts: ReportFacts) -> list[str]:
    """List the facts the operator needs, using only the formatted fact strings."""
    findings = [
        f"Verdict: {facts.verdict}.",
        f"Severity: {facts.severity}.",
        f"Flagged area: {facts.flagged_area_percent}.",
        f"Anomaly score: {facts.anomaly_score}.",
    ]
    if facts.region is not None:
        findings.append(f"Region: {facts.region}.")
    return findings
