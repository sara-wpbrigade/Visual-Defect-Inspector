"""Smoke test: send one image and fake facts to Gemini, print the validated JSON."""

import json
import logging
import sys
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)

GEMINI_API_VERSION = "v1beta"

IMAGE_MIME_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

FAKE_FACTS = {
    "verdict": "defect",
    "confidence": 0.91,
    "defect_type": "scratch",
    "severity": "medium",
    "action": "rework",
}


class ReportContent(BaseModel):
    """Structured report text the model must return."""

    summary: str
    findings: list[str]
    recommendation: str


def build_prompt(facts: dict[str, object]) -> str:
    """Build a prompt that treats the facts as fixed and the model as a writer only."""
    return (
        "You write short inspection reports for a factory QC operator. "
        "Use ONLY the facts below. Never invent defects, numbers or locations. "
        "Return JSON with: summary, findings (list), recommendation.\n\n"
        f"FACTS:\n{json.dumps(facts, indent=2)}"
    )


def load_image_part(path: Path) -> types.Part:
    """Read an image file and wrap it for the Gemini API."""
    mime_type = IMAGE_MIME_TYPES.get(path.suffix.lower())
    if mime_type is None:
        raise ValueError(f"Unsupported image type: {path.suffix}")
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)


def main() -> None:
    """Run the smoke test against the image path given on the command line."""
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) != 2:
        sys.exit("Usage: uv run python -m scripts.gemini_smoke_test <image path>")
    settings = get_settings()
    client = genai.Client(
        api_key=settings.gemini_api_key.get_secret_value(),
        http_options=types.HttpOptions(api_version=GEMINI_API_VERSION),
    )
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=[load_image_part(Path(sys.argv[1])), build_prompt(FAKE_FACTS)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ReportContent,
        ),
    )
    if response.text is None:
        sys.exit("Gemini returned no text.")
    report = ReportContent.model_validate_json(response.text)
    logger.info("Validated report:\n%s", report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
