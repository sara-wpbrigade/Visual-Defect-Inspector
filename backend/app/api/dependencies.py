"""Dependencies shared by the API routes."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.core.persona import PersonaConfig, load_persona
from app.models.detector import Detector
from app.models.factory import create_detector, create_report_writer
from app.models.report_writer import ReportWriter
from app.models.template_writer import TemplateReportWriter
from app.services.inspection import InspectionService
from app.services.report import ReportService, utc_now


@lru_cache
def get_detector() -> Detector:
    """Return the configured detector, loading the model once per process."""
    return create_detector(get_settings())


@lru_cache
def get_persona() -> PersonaConfig:
    """Return the configured persona, loading it once per process."""
    return load_persona(get_settings().persona_name)


def get_inspection_service(
    detector: Annotated[Detector, Depends(get_detector)],
    persona: Annotated[PersonaConfig, Depends(get_persona)],
) -> InspectionService:
    """Build the inspection service from its injected dependencies."""
    return InspectionService(detector=detector, persona=persona)


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
