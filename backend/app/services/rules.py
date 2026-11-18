"""Rules that turn detector output into verdict, severity and action."""

import numpy as np

from app.core.persona import PersonaConfig, SeverityBands
from app.schemas import Action, Assessment, DefectLocation, Severity, Verdict

BASE_CONFIDENCE = 0.5
GRID_SIDE = 3
GRID_REGIONS = (
    "upper left",
    "upper center",
    "upper right",
    "middle left",
    "center",
    "middle right",
    "lower left",
    "lower center",
    "lower right",
)


def area_ratio(mask: np.ndarray) -> float:
    """Return the fraction of mask pixels flagged as defective."""
    if mask.size == 0:
        raise ValueError("Mask must not be empty.")
    return float(np.count_nonzero(mask)) / mask.size


def locate_defect(mask: np.ndarray) -> DefectLocation | None:
    """Return the grid cell and normalized box of the flagged pixels.

    A one-dimensional mask has no location, so it returns None.
    """
    if mask.ndim != 2 or not np.any(mask):
        return None
    rows, columns = np.nonzero(mask)
    height, width = mask.shape
    bbox = (
        float(columns.min()) / width,
        float(rows.min()) / height,
        float(columns.max() + 1) / width,
        float(rows.max() + 1) / height,
    )
    return DefectLocation(region=_grid_region(rows, columns, height, width), bbox=bbox)


def _grid_region(rows: np.ndarray, columns: np.ndarray, height: int, width: int) -> str:
    """Map the centroid of the flagged pixels to one of the nine grid labels."""
    center_x = (float(columns.mean()) + 0.5) / width
    center_y = (float(rows.mean()) + 0.5) / height
    column_index = min(int(center_x * GRID_SIDE), GRID_SIDE - 1)
    row_index = min(int(center_y * GRID_SIDE), GRID_SIDE - 1)
    return GRID_REGIONS[row_index * GRID_SIDE + column_index]


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
    location = locate_defect(mask) if verdict is Verdict.DEFECT else None
    return Assessment(
        verdict=verdict,
        confidence=compute_confidence(score, persona),
        needs_review=review,
        severity=severity,
        area_ratio=ratio,
        action=decide_action(verdict, severity, review, persona),
        location=location,
    )
