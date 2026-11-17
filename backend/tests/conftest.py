"""Shared fixtures for the test suite."""

from collections.abc import Callable

import pytest

from app.core.persona import PersonaConfig
from app.models.detector import Detection
from app.services.inspection import InspectionService
from tests.fakes import PERSONA_DATA, StubDetector, make_detection


@pytest.fixture
def persona_data() -> dict[str, object]:
    """The raw config used by the fixed test persona."""
    return dict(PERSONA_DATA)


@pytest.fixture
def persona() -> PersonaConfig:
    """A fixed persona, so tests never depend on the tuned config file."""
    return PersonaConfig.model_validate(PERSONA_DATA)


@pytest.fixture
def detection_factory() -> Callable[..., Detection]:
    """Return a helper that builds detections with a chosen score and area."""
    return make_detection


@pytest.fixture
def service_factory(persona: PersonaConfig) -> Callable[..., InspectionService]:
    """Return a helper that builds a service around a stubbed detector."""

    def build(result: Detection | Exception) -> InspectionService:
        return InspectionService(detector=StubDetector(result), persona=persona)

    return build
