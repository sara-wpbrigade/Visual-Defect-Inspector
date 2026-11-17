"""Dependencies shared by the API routes."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import get_settings
from app.core.persona import PersonaConfig, load_persona
from app.models.detector import Detector
from app.models.factory import create_detector
from app.services.inspection import InspectionService


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
