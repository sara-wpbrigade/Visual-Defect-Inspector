"""Tests for the inspection rules and persona config."""

from typing import cast

import numpy as np
import pytest
from pydantic import ValidationError

from app.core.persona import PersonaConfig, load_persona
from app.schemas import Action, Severity, Verdict
from app.services import rules


def make_mask(flagged: int, total: int = 100) -> np.ndarray:
    """Build a flat boolean mask with `flagged` pixels set."""
    mask = np.zeros(total, dtype=bool)
    mask[:flagged] = True
    return mask


def make_pixel_mask(pixel: tuple[int, int], shape: tuple[int, int] = (9, 9)) -> np.ndarray:
    """Build a 2-D mask with only one flagged pixel."""
    mask = np.zeros(shape, dtype=bool)
    mask[pixel] = True
    return mask


def test_area_ratio_counts_flagged_pixels() -> None:
    """A quarter of flagged pixels gives a ratio of 0.25."""
    assert rules.area_ratio(make_mask(25)) == 0.25


def test_area_ratio_rejects_empty_mask() -> None:
    """An empty mask is an error, not a zero."""
    with pytest.raises(ValueError):
        rules.area_ratio(np.array([], dtype=bool))


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0.2, Verdict.PASS), (0.5, Verdict.DEFECT), (0.9, Verdict.DEFECT)],
)
def test_decide_verdict(score: float, expected: Verdict, persona: PersonaConfig) -> None:
    """Scores at or above the cutoff are defects."""
    assert rules.decide_verdict(score, persona) is expected


@pytest.mark.parametrize(
    ("pixel", "expected"),
    [
        ((0, 0), "upper left"),
        ((0, 3), "upper center"),
        ((0, 6), "upper right"),
        ((3, 0), "middle left"),
        ((3, 3), "center"),
        ((3, 6), "middle right"),
        ((6, 0), "lower left"),
        ((6, 3), "lower center"),
        ((6, 6), "lower right"),
    ],
)
def test_locate_defect_names_the_grid_cell(pixel: tuple[int, int], expected: str) -> None:
    """The centroid of the flagged pixels selects one of the nine cells."""
    location = rules.locate_defect(make_pixel_mask(pixel))
    assert location is not None
    assert location.region == expected


def test_locate_defect_returns_normalized_bbox() -> None:
    """The box is the flagged bounds divided by the image size."""
    mask = np.zeros((10, 10), dtype=bool)
    mask[2:5, 3:7] = True
    location = rules.locate_defect(mask)
    assert location is not None
    assert location.bbox == pytest.approx((0.3, 0.2, 0.7, 0.5))


def test_locate_defect_returns_none_for_an_empty_mask() -> None:
    """A two-dimensional mask with no flagged pixel has no location."""
    assert rules.locate_defect(np.zeros((4, 4), dtype=bool)) is None


def test_locate_defect_returns_none_for_a_one_dimensional_mask() -> None:
    """The flat masks used by the detector contract have no location."""
    assert rules.locate_defect(make_mask(3)) is None


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [
        (0.005, Severity.LOW),
        (0.01, Severity.LOW),
        (0.03, Severity.MEDIUM),
        (0.05, Severity.MEDIUM),
        (0.2, Severity.HIGH),
    ],
)
def test_classify_severity(ratio: float, expected: Severity, persona: PersonaConfig) -> None:
    """Band limits are inclusive upper bounds."""
    assert rules.classify_severity(ratio, persona.severity_bands) is expected


def test_assess_adds_location_for_a_defect(persona: PersonaConfig) -> None:
    """A defect gets the grid cell and box of the flagged pixels."""
    mask = np.zeros((10, 10), dtype=bool)
    mask[0:5, 0:5] = True
    result = rules.assess(0.9, mask, persona)
    assert result.location is not None
    assert result.location.region == "upper left"


def test_assess_has_no_location_for_a_pass(persona: PersonaConfig) -> None:
    """A passing item has no defect location, even if pixels were flagged."""
    result = rules.assess(0.2, make_pixel_mask((0, 0), (10, 10)), persona)
    assert result.location is None


def test_assess_clean_item_is_accepted(persona: PersonaConfig) -> None:
    """A low score with nothing flagged passes with no severity."""
    result = rules.assess(0.2, make_mask(0), persona)
    assert (result.verdict, result.severity, result.action) == (
        Verdict.PASS,
        Severity.NONE,
        Action.ACCEPT,
    )


def test_assess_large_defect_is_rejected(persona: PersonaConfig) -> None:
    """A high score with a large flagged area is high severity and rejected."""
    result = rules.assess(0.9, make_mask(30), persona)
    assert (result.severity, result.action) == (Severity.HIGH, Action.REJECT)
    assert not result.needs_review


def test_assess_borderline_score_needs_review(persona: PersonaConfig) -> None:
    """A score near the cutoff is flagged for re-inspection."""
    result = rules.assess(0.55, make_mask(3), persona)
    assert result.needs_review
    assert result.action is Action.RE_INSPECT


def test_shipped_persona_file_is_valid() -> None:
    """The real config file loads and passes validation."""
    assert load_persona("factory_qc_operator").name == "factory_qc_operator"


def test_persona_name_blocks_path_traversal() -> None:
    """A name that tries to leave the config folder is rejected."""
    with pytest.raises(ValueError):
        load_persona("../secrets")


def test_persona_rejects_unordered_bands(persona_data: dict[str, object]) -> None:
    """Severity bands must increase."""
    bad = {**persona_data, "severity_bands": {"low_max": 0.1, "medium_max": 0.05}}
    with pytest.raises(ValidationError):
        PersonaConfig.model_validate(bad)


def test_persona_requires_action_text_for_every_action(
    persona_data: dict[str, object],
) -> None:
    """A missing action sentence is a config error."""
    action_text = dict(cast(dict[str, str], persona_data["action_text"]))
    del action_text["reject"]
    with pytest.raises(ValidationError):
        PersonaConfig.model_validate({**persona_data, "action_text": action_text})


def test_persona_rejects_blank_action_text(persona_data: dict[str, object]) -> None:
    """An empty action sentence is a config error."""
    action_text = dict(cast(dict[str, str], persona_data["action_text"]))
    action_text["accept"] = "  "
    with pytest.raises(ValidationError):
        PersonaConfig.model_validate({**persona_data, "action_text": action_text})
