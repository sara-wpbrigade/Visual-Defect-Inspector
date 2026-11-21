"""Pick the detector and report-writer implementations named by configuration."""

from pathlib import Path

from app.core.config import MILLISECONDS_PER_SECOND, ReportWriterKind, Settings
from app.models.detector import Detector
from app.models.report_writer import ReportWriter
from app.models.template_writer import TemplateReportWriter
from app.models.transcriber import Transcriber

GEMINI_SETTINGS_ERROR = "Gemini report writing requires GEMINI_API_KEY and GEMINI_MODEL."


def create_detector(checkpoint_path: Path, device: str) -> Detector:
    """Return a PatchCore detector for the given checkpoint.

    The import is deferred because loading Anomalib and Torch costs seconds and
    hundreds of megabytes, which the health check and the test suite never need.
    """
    from app.models.patchcore import PatchCoreDetector

    return PatchCoreDetector(checkpoint_path, device)


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
    if settings.gemini_api_key is None or settings.gemini_model is None:
        raise ValueError(GEMINI_SETTINGS_ERROR)
    from google import genai
    from google.genai import types

    from app.models.gemini_writer import GeminiReportWriter

    timeout_ms = int(settings.report_timeout_seconds * MILLISECONDS_PER_SECOND)
    client = genai.Client(
        api_key=settings.gemini_api_key.get_secret_value(),
        http_options=types.HttpOptions(
            api_version=settings.gemini_api_version,
            timeout=timeout_ms,
        ),
    )
    return GeminiReportWriter(
        client,
        settings.gemini_model,
        image_max_side=settings.report_image_max_side,
        include_image=settings.report_include_image,
    )
