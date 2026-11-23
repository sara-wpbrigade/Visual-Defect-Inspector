"""Pick the detector, classifier and report-writer implementations named by configuration."""

from pathlib import Path
from typing import Any

from app.core.categories import CategoryCatalog, CategoryConfig
from app.core.config import (
    MILLISECONDS_PER_SECOND,
    DetectorKind,
    ReportWriterKind,
    Settings,
)
from app.models.category_classifier import CategoryClassifier
from app.models.detector import Detector
from app.models.report_writer import ReportWriter
from app.models.template_writer import TemplateReportWriter
from app.models.transcriber import Transcriber

GEMINI_SETTINGS_ERROR = "Gemini report writing requires GEMINI_API_KEY and GEMINI_MODEL."
GEMINI_DETECTOR_SETTINGS_ERROR = "Gemini detection requires GEMINI_API_KEY and GEMINI_MODEL."
GEMINI_DETECTOR_CATEGORY_ERROR = "Gemini detection requires a category configuration."


def _create_gemini_client(settings: Settings, error_message: str) -> tuple[Any, str]:
    """Build a configured Gemini SDK client or raise if credentials are missing."""
    if settings.gemini_api_key is None or settings.gemini_model is None:
        raise ValueError(error_message)
    from google import genai
    from google.genai import types

    timeout_ms = int(settings.report_timeout_seconds * MILLISECONDS_PER_SECOND)
    client = genai.Client(
        api_key=settings.gemini_api_key.get_secret_value(),
        http_options=types.HttpOptions(
            api_version=settings.gemini_api_version,
            timeout=timeout_ms,
        ),
    )
    return client, settings.gemini_model


def create_detector(
    checkpoint_path: Path,
    device: str,
    settings: Settings | None = None,
    category: CategoryConfig | None = None,
) -> Detector:
    """Return the configured detector for a category.

    Calls without *settings* keep the historical PatchCore behavior, so existing
    ``create_detector(checkpoint, device)`` callers are unaffected. When Gemini
    is selected, *category* is required and the checkpoint path is not read; the
    Google SDK and the detector module are imported only in that branch.
    """
    if settings is not None and settings.detector is DetectorKind.GEMINI:
        return _create_gemini_detector(settings, category)

    # The import is deferred because loading Anomalib and Torch costs seconds and
    # hundreds of megabytes, which the health check and the test suite never need.
    from app.models.patchcore import PatchCoreDetector

    return PatchCoreDetector(checkpoint_path, device)


def _create_gemini_detector(settings: Settings, category: CategoryConfig | None) -> Detector:
    """Build a Gemini vision detector without touching a PatchCore checkpoint."""
    if category is None:
        raise ValueError(GEMINI_DETECTOR_CATEGORY_ERROR)
    from app.models.gemini import GeminiDetector

    client, model = _create_gemini_client(settings, GEMINI_DETECTOR_SETTINGS_ERROR)
    return GeminiDetector(
        client,
        model,
        category,
        votes=settings.gemini_vision_votes,
        temperature=settings.gemini_vision_temperature,
        zoom=settings.gemini_vision_zoom,
        verify=settings.gemini_vision_verify,
        max_side=settings.gemini_vision_max_side,
        retries=settings.gemini_vision_retries,
    )


def create_category_classifier(catalog: CategoryCatalog, settings: Settings) -> CategoryClassifier:
    """Return the category-gate classifier matching the configured detector backend."""
    if settings.detector is DetectorKind.GEMINI:
        from app.models.gemini_classifier import GeminiCategoryClassifier

        client, model = _create_gemini_client(settings, GEMINI_DETECTOR_SETTINGS_ERROR)
        return GeminiCategoryClassifier(
            client,
            model,
            catalog,
            max_side=settings.gemini_vision_max_side,
            retries=settings.gemini_vision_retries,
        )

    from app.models.embedding_classifier import EmbeddingCategoryClassifier

    return EmbeddingCategoryClassifier(catalog, device=settings.detector_device)


def create_transcriber(settings: Settings) -> Transcriber:
    """Return the configured transcriber, importing Whisper only when a note needs it.

    Loading the speech model is slow and only inspections that carry a voice
    note need it, so the import and the model load are both deferred.
    """
    from app.models.whisper_transcriber import FasterWhisperTranscriber

    return FasterWhisperTranscriber(
        settings.whisper_model, settings.whisper_device, settings.whisper_compute_type
    )


def create_report_writer(settings: Settings) -> ReportWriter:
    """Return the configured report writer, importing the Google SDK only if needed."""
    if settings.report_writer is ReportWriterKind.TEMPLATE:
        return TemplateReportWriter()
    from app.models.gemini_writer import GeminiReportWriter

    client, model = _create_gemini_client(settings, GEMINI_SETTINGS_ERROR)
    return GeminiReportWriter(
        client,
        model,
        image_max_side=settings.report_image_max_side,
        include_image=settings.report_include_image,
    )
