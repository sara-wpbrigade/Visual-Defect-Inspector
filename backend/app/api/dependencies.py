"""Dependencies shared by the API routes."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.categories import CategoryCatalog, load_categories
from app.core.config import Settings, get_settings
from app.core.persona import PersonaConfig, load_persona
from app.models.embedding_classifier import EmbeddingCategoryClassifier
from app.models.factory import create_report_writer, create_transcriber
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


@lru_cache
def get_category_catalog() -> CategoryCatalog:
    """Load the enabled and available categories once per process."""
    settings = get_settings()
    return load_categories(settings.categories_dir, settings.enabled_category_ids())


@lru_cache
def get_detector_registry() -> DetectorRegistry:
    """Return the lazy per-category detector registry."""
    settings = get_settings()
    return DetectorRegistry(get_category_catalog(), settings.detector_device)


@lru_cache
def get_persona() -> PersonaConfig:
    """Return the configured persona, loading it once per process."""
    return load_persona(get_settings().persona_name)


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


@lru_cache
def get_category_verifier() -> CategoryVerifier:
    """Return the yes/no category gate backed by the embedding classifier."""
    catalog = get_category_catalog()
    classifier = EmbeddingCategoryClassifier(catalog, device=get_settings().detector_device)
    return CategoryVerifier(catalog, classifier)


@lru_cache
def get_transcriber() -> Transcriber:
    """Return the configured transcriber, loading the speech model once per process."""
    return create_transcriber(get_settings())


def get_voice_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> VoiceNoteService:
    """Build the voice service; the speech model loads only when a note needs it."""
    return VoiceNoteService(get_transcriber, settings.max_transcript_chars)


@lru_cache
def get_report_writer() -> ReportWriter:
    """Return the configured report writer, building it once per process."""
    return create_report_writer(get_settings())


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
