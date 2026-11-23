"""Dependencies shared by the API routes."""

import threading
from typing import Annotated

from fastapi import Depends

from app.core.categories import CategoryCatalog, load_categories
from app.core.config import Settings, get_settings
from app.core.persona import PersonaConfig, load_persona
from app.models.factory import create_category_classifier, create_report_writer, create_transcriber
from app.models.registry import DetectorRegistry
from app.models.report_writer import ReportWriter
from app.models.template_writer import TemplateReportWriter
from app.models.transcriber import Transcriber
from app.services.category_verifier import CategoryVerifier
from app.services.inspection import InspectionService
from app.services.report import ReportService, utc_now
from app.services.repository import InspectionRepository, SqliteInspectionRepository
from app.services.storage import ArtifactStore
from app.services.voice import VoiceNoteService

# These providers are process-wide singletons whose construction reads config or
# loads models. A bare ``lru_cache`` does not stop two threads from building the
# same provider twice, so each cache is filled once under an explicit lock.
_CACHE_LOCK = threading.RLock()
_category_catalog: CategoryCatalog | None = None
_detector_registry: DetectorRegistry | None = None
_persona: PersonaConfig | None = None
_category_verifier: CategoryVerifier | None = None
_transcriber: Transcriber | None = None
_report_writer: ReportWriter | None = None


def get_category_catalog() -> CategoryCatalog:
    """Load the enabled and available categories once per process."""
    global _category_catalog
    cached = _category_catalog
    if cached is not None:
        return cached
    with _CACHE_LOCK:
        cached = _category_catalog
        if cached is None:
            settings = get_settings()
            cached = load_categories(settings.categories_dir, settings.enabled_category_ids())
            _category_catalog = cached
        return cached


def get_detector_registry() -> DetectorRegistry:
    """Return the lazy per-category detector registry."""
    global _detector_registry
    cached = _detector_registry
    if cached is not None:
        return cached
    with _CACHE_LOCK:
        cached = _detector_registry
        if cached is None:
            settings = get_settings()
            cached = DetectorRegistry(
                get_category_catalog(), settings.detector_device, settings=settings
            )
            _detector_registry = cached
        return cached


def get_persona() -> PersonaConfig:
    """Return the configured persona, loading it once per process."""
    global _persona
    cached = _persona
    if cached is not None:
        return cached
    with _CACHE_LOCK:
        cached = _persona
        if cached is None:
            cached = load_persona(get_settings().persona_name)
            _persona = cached
        return cached


def get_inspection_service(
    registry: Annotated[DetectorRegistry, Depends(get_detector_registry)],
    persona: Annotated[PersonaConfig, Depends(get_persona)],
) -> InspectionService:
    """Build the inspection service from the registry and base persona."""
    return InspectionService(registry=registry, base_persona=persona)


def get_persona_by_category() -> dict[str, PersonaConfig]:
    """Map each available category id to an effective PersonaConfig."""
    settings = get_settings()
    catalog = get_category_catalog()
    base = load_persona(settings.persona_name)
    return {c.id: base.for_category(c) for c in catalog.all()}


def get_category_verifier() -> CategoryVerifier:
    """Return the yes/no category gate backed by the configured classifier."""
    global _category_verifier
    cached = _category_verifier
    if cached is not None:
        return cached
    with _CACHE_LOCK:
        cached = _category_verifier
        if cached is None:
            settings = get_settings()
            catalog = get_category_catalog()
            classifier = create_category_classifier(catalog, settings)
            cached = CategoryVerifier(catalog, classifier)
            _category_verifier = cached
        return cached


def get_transcriber() -> Transcriber:
    """Return the configured transcriber, loading the speech model once per process."""
    global _transcriber
    cached = _transcriber
    if cached is not None:
        return cached
    with _CACHE_LOCK:
        cached = _transcriber
        if cached is None:
            cached = create_transcriber(get_settings())
            _transcriber = cached
        return cached


def get_voice_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> VoiceNoteService:
    """Build the voice service; the speech model loads only when a note needs it."""
    return VoiceNoteService(get_transcriber, settings.max_transcript_chars)


def get_report_writer() -> ReportWriter:
    """Return the configured report writer, building it once per process."""
    global _report_writer
    cached = _report_writer
    if cached is not None:
        return cached
    with _CACHE_LOCK:
        cached = _report_writer
        if cached is None:
            cached = create_report_writer(get_settings())
            _report_writer = cached
        return cached


def get_report_service(
    writer: Annotated[ReportWriter, Depends(get_report_writer)],
    persona: Annotated[PersonaConfig, Depends(get_persona)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReportService:
    """Build the report service with the configured writer and template fallback."""
    return ReportService(
        writer=writer,
        fallback_writer=TemplateReportWriter(),
        persona=persona,
        max_attempts=settings.report_max_attempts,
        max_transcript_chars=settings.max_transcript_chars,
        clock=utc_now,
    )


def build_repository(settings: Settings) -> SqliteInspectionRepository:
    """Return the repository over the configured database file."""
    return SqliteInspectionRepository(settings.database_path)


def get_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> InspectionRepository:
    """Return the inspection repository for one request."""
    return build_repository(settings)


def get_artifact_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ArtifactStore:
    """Return the artifact store over the configured upload folder."""
    return ArtifactStore(settings.upload_dir)
