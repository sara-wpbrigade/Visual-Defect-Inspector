"""Tests for the Gemini report writer with an injected fake client."""

import io
from types import SimpleNamespace
from typing import Any, cast

import pytest
from google import genai
from google.genai import types
from PIL import Image

from app.core.persona import PersonaConfig
from app.models.gemini_writer import GeminiReportWriter
from app.models.report_prompt import SYSTEM_INSTRUCTION
from app.models.report_writer import ReportWriterError
from app.schemas import (
    Action,
    Assessment,
    InspectionOutcome,
    ReportDraft,
    ReportSource,
    Severity,
    Verdict,
)
from app.services.report_facts import ReportFacts, build_report_facts
from tests.fakes import make_draft

MODEL_NAME = "test-model"
MAX_SIDE = 8
PHOTO_SIZE = (20, 10)
EXPECTED_PHOTO_SIZE = (8, 4)


class FakeModels:
    """Record calls and return an injected response or error."""

    def __init__(self, response: object | None = None, error: Exception | None = None) -> None:
        """Store the result of the next call."""
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def generate_content(
        self, *, model: str, contents: object, config: types.GenerateContentConfig
    ) -> object:
        """Record the request and return the injected result."""
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    """Stand-in for genai.Client that only exposes models."""

    def __init__(self, models: FakeModels) -> None:
        """Store the fake models service."""
        self.models = models


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


def make_writer(models: FakeModels, include_image: bool = True) -> GeminiReportWriter:
    """Build the writer around a cast fake client."""
    client = cast(genai.Client, FakeClient(models))
    return GeminiReportWriter(
        client, MODEL_NAME, image_max_side=MAX_SIDE, include_image=include_image
    )


def test_request_uses_the_instruction_json_mode_and_draft_schema(
    persona: PersonaConfig,
) -> None:
    """The provider call must constrain the response to our draft schema."""
    draft = make_draft(defect_type="scratch")
    models = FakeModels(response=SimpleNamespace(text=draft.model_dump_json()))
    writer = make_writer(models)
    assert writer.source is ReportSource.AI
    result = writer.write(make_facts(persona), None, None)
    assert result == draft
    call = models.calls[0]
    assert call["model"] == MODEL_NAME
    config = call["config"]
    assert config.system_instruction == SYSTEM_INSTRUCTION
    assert config.response_mime_type == "application/json"
    assert config.response_schema is ReportDraft
    contents = call["contents"]
    assert isinstance(contents, types.Content)
    parts = contents.parts
    assert parts is not None
    assert len(parts) == 1
    assert parts[0].text is not None
    assert "93.7%" in parts[0].text


def test_photo_is_attached_and_downscaled(persona: PersonaConfig) -> None:
    """The longest side of the photo is capped before it is sent."""
    draft = make_draft(defect_type="scratch")
    models = FakeModels(response=SimpleNamespace(text=draft.model_dump_json()))
    image = Image.new("RGB", PHOTO_SIZE, color=(120, 20, 20))
    make_writer(models).write(make_facts(persona), image, None)
    contents = models.calls[0]["contents"]
    assert isinstance(contents, types.Content)
    parts = contents.parts
    assert parts is not None
    assert len(parts) == 2
    part = parts[1]
    assert part.inline_data is not None
    assert part.inline_data.mime_type == "image/jpeg"
    data = part.inline_data.data
    assert data is not None
    with Image.open(io.BytesIO(data)) as decoded:
        assert decoded.size == EXPECTED_PHOTO_SIZE


def test_photo_is_omitted_when_disabled(persona: PersonaConfig) -> None:
    """Configuration can switch the photo off without breaking the call."""
    draft = make_draft(defect_type="scratch")
    models = FakeModels(response=SimpleNamespace(text=draft.model_dump_json()))
    image = Image.new("RGB", PHOTO_SIZE)
    make_writer(models, include_image=False).write(make_facts(persona), image, None)
    contents = models.calls[0]["contents"]
    assert isinstance(contents, types.Content)
    parts = contents.parts
    assert parts is not None
    assert len(parts) == 1


def test_provider_error_becomes_a_writer_error(persona: PersonaConfig) -> None:
    """A provider crash is wrapped so the service can fall back."""
    models = FakeModels(error=RuntimeError("provider down"))
    with pytest.raises(ReportWriterError):
        make_writer(models).write(make_facts(persona), None, None)


@pytest.mark.parametrize("text", [None, ""])
def test_missing_response_text_becomes_a_writer_error(
    persona: PersonaConfig, text: str | None
) -> None:
    """An empty answer is a writer failure, not an empty draft."""
    models = FakeModels(response=SimpleNamespace(text=text))
    with pytest.raises(ReportWriterError):
        make_writer(models).write(make_facts(persona), None, None)


def test_invalid_json_becomes_a_writer_error(persona: PersonaConfig) -> None:
    """Malformed model output never escapes as untrusted data."""
    models = FakeModels(response=SimpleNamespace(text="{not json"))
    with pytest.raises(ReportWriterError):
        make_writer(models).write(make_facts(persona), None, None)
