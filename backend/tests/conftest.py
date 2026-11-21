"""Shared fixtures for the test suite."""

from collections.abc import Callable

import pytest

from app.core.categories import CategoryCatalog, CategoryConfig
from app.core.persona import PersonaConfig
from app.models.detector import Detection
from app.models.transcriber import Transcript
from app.services.inspection import InspectionService
from app.services.voice import VoiceNoteService
from tests.fakes import (
    PERSONA_DATA,
    StubDetector,
    StubDetectorRegistry,
    StubTranscriber,
    make_catalog,
    make_category_config,
    make_detection,
)

MAX_TEST_TRANSCRIPT_CHARS = 100


@pytest.fixture
def persona_data() -> dict[str, object]:
    """The raw config used by the fixed test persona."""
    return dict(PERSONA_DATA)


@pytest.fixture
def persona() -> PersonaConfig:
    """A fixed persona, so tests never depend on the tuned config file."""
    return PersonaConfig.model_validate(PERSONA_DATA)


@pytest.fixture
def category_config() -> CategoryConfig:
    """A generic category whose bands match the test persona."""
    return make_category_config()


@pytest.fixture
def category_catalog(category_config: CategoryConfig) -> CategoryCatalog:
    """A catalog containing the generic test category."""
    return make_catalog(category_config)


@pytest.fixture
def detection_factory() -> Callable[..., Detection]:
    """Return a helper that builds detections with a chosen score and area."""
    return make_detection


@pytest.fixture
def service_factory(persona: PersonaConfig) -> Callable[..., InspectionService]:
    """Return a helper that builds a service around a stubbed detector."""

    def build(result: Detection | Exception) -> InspectionService:
        detector = StubDetector(result)
        registry = StubDetectorRegistry(detector)
        return InspectionService(registry=registry, base_persona=persona)

    return build


@pytest.fixture
def voice_factory() -> Callable[..., tuple[VoiceNoteService, StubTranscriber]]:
    """Return a helper that builds a voice service and the stub it uses."""

    def build(result: Transcript | Exception) -> tuple[VoiceNoteService, StubTranscriber]:
        stub = StubTranscriber(result)
        return VoiceNoteService(lambda: stub, MAX_TEST_TRANSCRIPT_CHARS), stub

    return build
