"""Rules that turn detector output into verdict, severity and action."""

import numpy as np

from app.core.persona import PersonaConfig, SeverityBands
from app.schemas import Action, Assessment, Severity, Verdict

BASE_CONFIDENCE = 0.5


def area_ratio(mask: np.ndarray) -> float:
    """Return the fraction of mask pixels flagged as defective."""
    if mask.size == 0:
        raise ValueError("Mask must not be empty.")
    return float(np.count_nonzero(mask)) / mask.size


def decide_verdict(score: float, persona: PersonaConfig) -> Verdict:
    """Return DEFECT when the score reaches the persona's cutoff."""
    return Verdict.DEFECT if score >= persona.decision_cutoff else Verdict.PASS


def compute_confidence(score: float, persona: PersonaConfig) -> float:
    """Return 0.5 at the cutoff, rising towards 1.0 as the score moves away from it."""
    distance = abs(score - persona.decision_cutoff)
    return min(1.0, BASE_CONFIDENCE + distance)


def needs_review(score: float, persona: PersonaConfig) -> bool:
    """Return True when the score is too close to the cutoff to trust."""
    return abs(score - persona.decision_cutoff) < persona.review_margin


def classify_severity(ratio: float, bands: SeverityBands) -> Severity:
    """Map the flagged-area ratio to a defect severity."""
    if ratio <= bands.low_max:
        return Severity.LOW
    if ratio <= bands.medium_max:
        return Severity.MEDIUM
    return Severity.HIGH


def decide_action(
    verdict: Verdict, severity: Severity, review: bool, persona: PersonaConfig
) -> Action:
    """Look up the recommended action in the persona's action table."""
    if review:
        return persona.on_uncertain
    if verdict is Verdict.PASS:
        return persona.on_pass
    return persona.on_defect[severity]


def assess(score: float, mask: np.ndarray, persona: PersonaConfig) -> Assessment:
    """Combine all rules into one assessment of an inspected item."""
    verdict = decide_verdict(score, persona)
    ratio = area_ratio(mask)
    severity = (
        Severity.NONE
        if verdict is Verdict.PASS
        else classify_severity(ratio, persona.severity_bands)
    )
    review = needs_review(score, persona)
    return Assessment(
        verdict=verdict,
        confidence=compute_confidence(score, persona),
        needs_review=review,
        severity=severity,
        area_ratio=ratio,
        action=decide_action(verdict, severity, review, persona),
    )
