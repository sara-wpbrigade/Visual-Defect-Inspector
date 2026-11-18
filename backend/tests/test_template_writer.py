"""Tests for the deterministic, offline report template."""

import re

import numpy as np
import pytest

from app.core.persona import PersonaConfig
from app.models.template_writer import TemplateReportWriter
from app.schemas import Action, InspectionOutcome, ReportSource
from app.services import rules
from app.services.report_facts import build_report_facts

NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
MASK_SIZE = 100


def make_mask(flagged: int) -> np.ndarray:
    """Build a flat mask with the requested number of flagged pixels."""
    mask = np.zeros(MASK_SIZE, dtype=bool)
    mask[:flagged] = True
    return mask


@pytest.mark.parametrize(
    ("action", "score", "flagged"),
    [
        (Action.ACCEPT, 0.2, 0),
        (Action.REJECT, 0.9, 30),
        (Action.REWORK, 0.9, 1),
        (Action.RE_INSPECT, 0.55, 3),
    ],
)
def test_template_uses_the_persona_action_sentence(
    persona: PersonaConfig, action: Action, score: float, flagged: int
) -> None:
    """Each action maps to its configured sentence, with no defect guess."""
    outcome = InspectionOutcome(
        score=score, assessment=rules.assess(score, make_mask(flagged), persona)
    )
    facts = build_report_facts(outcome, persona)
    assert facts.action is action
    draft = TemplateReportWriter().write(facts, None, None)
    assert draft.recommendations == [persona.action_text[action]]
    assert draft.defect_type is None
    assert draft.voice_note_conflict is None


def test_template_declares_its_source() -> None:
    """The service reads the source from the writer itself."""
    assert TemplateReportWriter().source is ReportSource.TEMPLATE


def test_template_is_deterministic(persona: PersonaConfig) -> None:
    """The same facts always produce the same draft."""
    outcome = InspectionOutcome(score=0.9, assessment=rules.assess(0.9, make_mask(30), persona))
    facts = build_report_facts(outcome, persona)
    writer = TemplateReportWriter()
    assert writer.write(facts, None, None) == writer.write(facts, None, None)


def test_template_adds_no_numbers_beyond_the_facts(persona: PersonaConfig) -> None:
    """The template may only repeat the numbers already formatted in the facts."""
    outcome = InspectionOutcome(score=0.9, assessment=rules.assess(0.9, make_mask(30), persona))
    facts = build_report_facts(outcome, persona)
    draft = TemplateReportWriter().write(facts, None, None)
    allowed = set(NUMBER_PATTERN.findall(facts.model_dump_json()))
    used = set(
        NUMBER_PATTERN.findall(" ".join([draft.summary, *draft.findings, *draft.recommendations]))
    )
    assert used <= allowed


def test_template_names_the_region_for_a_defect(persona: PersonaConfig) -> None:
    """A two-dimensional mask gives the summary and findings a grid cell."""
    mask = np.zeros((10, 10), dtype=bool)
    mask[0:2, 0:2] = True
    outcome = InspectionOutcome(score=0.9, assessment=rules.assess(0.9, mask, persona))
    facts = build_report_facts(outcome, persona)
    draft = TemplateReportWriter().write(facts, None, None)
    assert "upper left" in draft.summary
    assert "Region: upper left." in draft.findings
