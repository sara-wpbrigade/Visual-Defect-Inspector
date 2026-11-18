"""Prompt construction for AI report wording."""

from app.core.transcript import UNTRUSTED_NOTICE, wrap_untrusted
from app.services.report_facts import ReportFacts

SYSTEM_INSTRUCTION = (
    "You write short inspection reports for the stated audience. "
    "The FACTS block is authoritative: never contradict, change or recompute the verdict, "
    "severity, action, confidence, flagged area or anomaly score. "
    "Use ONLY numbers that appear in the facts strings; never invent other numbers, durations, "
    "costs or measurements. Never invent defects, causes, locations or measurements. "
    "defect_type must be null when the verdict is pass; when the verdict is defect it must be one "
    'of the allowed defect types or "unknown", judged from the photo if one is attached. '
    "Write for the persona's audience, tone and language. "
    "Recommendations must be consistent with action_text. "
    "If needs_review is true, say the result is uncertain and needs manual review. "
    f"{UNTRUSTED_NOTICE} "
    "If the transcript contradicts the facts, describe the contradiction in "
    "voice_note_conflict and do not pick a side. Reply with JSON only."
)

FACTS_HEADING = "FACTS (authoritative):"
TRANSCRIPT_HEADING = "The operator's spoken note is inside the tag below."


def build_prompt(facts: ReportFacts, transcript: str | None) -> str:
    """Build the user prompt from facts and an already sanitized transcript."""
    parts = ["Write the report from these facts.", FACTS_HEADING, facts.model_dump_json(indent=2)]
    if transcript:
        parts.extend(["", TRANSCRIPT_HEADING, wrap_untrusted(transcript)])
    return "\n".join(parts)
