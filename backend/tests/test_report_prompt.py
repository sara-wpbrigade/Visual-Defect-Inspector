"""Tests for the AI report prompt and its untrusted-transcript block."""

from app.core.persona import PersonaConfig
from app.core.transcript import TRANSCRIPT_TAG, UNTRUSTED_NOTICE, wrap_untrusted
from app.models.report_prompt import (
    FACTS_HEADING,
    SYSTEM_INSTRUCTION,
    TRANSCRIPT_HEADING,
    build_prompt,
)
from app.schemas import Action, Assessment, InspectionOutcome, Severity, Verdict
from app.services.report_facts import ReportFacts, build_report_facts

TRANSCRIPT = "The operator saw a crack in the north field."


def make_facts(persona: PersonaConfig) -> ReportFacts:
    """Return fixed facts for the defect case."""
    outcome = InspectionOutcome(
        score=0.937,
        assessment=Assessment(
            verdict=Verdict.DEFECT,
            confidence=0.937,
            needs_review=False,
            severity=Severity.HIGH,
            area_ratio=0.175,
            action=Action.REJECT,
        ),
    )
    return build_report_facts(outcome, persona)


def test_prompt_embeds_the_preformatted_facts(persona: PersonaConfig) -> None:
    """The facts block carries the exact strings the model may reuse."""
    prompt = build_prompt(make_facts(persona), None)
    assert FACTS_HEADING in prompt
    assert "93.7%" in prompt
    assert "17.5%" in prompt
    assert "0.937" in prompt


def test_prompt_has_no_transcript_block_when_absent(persona: PersonaConfig) -> None:
    """No note means no tag and no transcript heading."""
    prompt = build_prompt(make_facts(persona), None)
    assert TRANSCRIPT_HEADING not in prompt
    assert f"<{TRANSCRIPT_TAG}" not in prompt


def test_prompt_wraps_a_transcript_as_untrusted(persona: PersonaConfig) -> None:
    """A note is fenced with the exact tag the instruction describes."""
    prompt = build_prompt(make_facts(persona), TRANSCRIPT)
    assert TRANSCRIPT_HEADING in prompt
    assert wrap_untrusted(TRANSCRIPT) in prompt


def test_instruction_states_the_guardrails() -> None:
    """The system instruction names the tag and demands JSON only."""
    assert UNTRUSTED_NOTICE in SYSTEM_INSTRUCTION
    assert "authoritative" in SYSTEM_INSTRUCTION
    assert "JSON only" in SYSTEM_INSTRUCTION
