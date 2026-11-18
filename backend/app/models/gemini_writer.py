"""Gemini implementation of the report writer."""

import io
import logging

from google import genai
from google.genai import types
from PIL import Image
from pydantic import ValidationError

from app.models.report_prompt import SYSTEM_INSTRUCTION, build_prompt
from app.models.report_writer import ReportWriterError
from app.schemas import ReportDraft, ReportSource
from app.services.report_facts import ReportFacts

logger = logging.getLogger(__name__)

JSON_MIME_TYPE = "application/json"
JPEG_MIME_TYPE = "image/jpeg"
JPEG_FORMAT = "JPEG"
JPEG_QUALITY = 90
REPORT_WRITER_ERROR = "The report writer could not produce a draft."


class GeminiReportWriter:
    """Ask Gemini for report wording, with the client injected for tests."""

    source = ReportSource.AI

    def __init__(
        self,
        client: genai.Client,
        model: str,
        *,
        image_max_side: int,
        include_image: bool,
    ) -> None:
        """Store the client and the image-handling settings."""
        self._client = client
        self._model = model
        self._image_max_side = image_max_side
        self._include_image = include_image

    def write(
        self, facts: ReportFacts, image: Image.Image | None, transcript: str | None
    ) -> ReportDraft:
        """Return the model's draft, raising ReportWriterError on any failure."""
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=self._contents(facts, image, transcript),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type=JSON_MIME_TYPE,
                    response_schema=ReportDraft,
                ),
            )
        except Exception as exc:
            logger.exception("The report provider call failed")
            raise ReportWriterError(REPORT_WRITER_ERROR) from exc
        if not response.text:
            logger.warning("The report provider returned no text")
            raise ReportWriterError(REPORT_WRITER_ERROR)
        try:
            return ReportDraft.model_validate_json(response.text)
        except ValidationError as exc:
            # The validation message can contain model text, so log no traceback.
            logger.warning("The report provider returned invalid JSON")
            raise ReportWriterError(REPORT_WRITER_ERROR) from exc

    def _contents(
        self, facts: ReportFacts, image: Image.Image | None, transcript: str | None
    ) -> types.Content:
        """Build the prompt content and, when enabled, the downscaled photo part."""
        parts = [types.Part(text=build_prompt(facts, transcript))]
        if image is None or not self._include_image:
            return types.Content(parts=parts)
        parts.append(_image_part(image, self._image_max_side))
        return types.Content(parts=parts)


def _image_part(image: Image.Image, max_side: int) -> types.Part:
    """Downscale the photo and encode it as a JPEG part."""
    prepared = image.copy()
    prepared.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    prepared.convert("RGB").save(buffer, format=JPEG_FORMAT, quality=JPEG_QUALITY)
    return types.Part.from_bytes(data=buffer.getvalue(), mime_type=JPEG_MIME_TYPE)
