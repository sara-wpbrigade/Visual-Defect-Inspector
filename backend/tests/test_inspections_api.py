"""API tests for POST /inspections with a stubbed detector."""

import io
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from PIL import Image
from pydantic import SecretStr

from app.api.dependencies import get_detector, get_persona
from app.core.config import Settings, get_settings
from app.core.persona import PersonaConfig
from app.main import app
from app.models.detector import Detection
from tests.fakes import StubDetector

PNG_CONTENT_TYPE = "image/png"
TINY_BYTE_LIMIT = 20
TINY_PIXEL_LIMIT = 100

DetectionFactory = Callable[..., Detection]


def make_png(size: tuple[int, int] = (10, 10)) -> bytes:
    """Return a small valid PNG as bytes."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(180, 60, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


def upload(client: TestClient, data: bytes, name: str = "photo.png") -> Response:
    """Post image bytes to the inspection endpoint."""
    return client.post("/inspections", files={"image": (name, data, PNG_CONTENT_TYPE)})


@pytest.fixture
def api_factory(tmp_path: Path, persona: PersonaConfig) -> Iterator[Callable[..., TestClient]]:
    """Build clients with the model, persona and settings under test control."""
    base = Settings(
        gemini_api_key=SecretStr("test-key"),
        gemini_model="test-model",
        upload_dir=tmp_path,
    )

    def build(result: Detection | Exception, **overrides: object) -> TestClient:
        settings = base.model_copy(update=dict(overrides))
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_persona] = lambda: persona
        app.dependency_overrides[get_detector] = lambda: StubDetector(result)
        return TestClient(app)

    yield build
    app.dependency_overrides.clear()


def test_defect_returns_reject(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """A high score with a large flagged area comes back as a reject."""
    response = upload(api_factory(detection_factory(0.9, 30)), make_png())
    assert response.status_code == 201
    body = response.json()
    assert body["assessment"]["verdict"] == "defect"
    assert body["assessment"]["severity"] == "high"
    assert body["assessment"]["action"] == "reject"


def test_pass_returns_accept(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """A clean photo comes back as a pass with an accept action."""
    response = upload(api_factory(detection_factory(0.2)), make_png())
    body = response.json()
    assert body["assessment"]["verdict"] == "pass"
    assert body["assessment"]["action"] == "accept"
    assert body["assessment"]["needs_review"] is False


def test_photo_is_stored_under_the_inspection_id(
    api_factory: Callable[..., TestClient],
    detection_factory: DetectionFactory,
    tmp_path: Path,
) -> None:
    """The upload is written once, with the returned id as its filename."""
    response = upload(api_factory(detection_factory(0.2)), make_png())
    assert [path.stem for path in tmp_path.glob("*.png")] == [response.json()["inspection_id"]]


def test_non_image_upload_is_rejected(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """Text sent as a photo is a 400, whatever the filename says."""
    client = api_factory(detection_factory(0.2))
    response = upload(client, b"this is not an image", "notes.txt")
    assert response.status_code == 400
    assert "valid image" in response.json()["detail"]


def test_empty_upload_is_rejected(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """Zero bytes are a 400."""
    assert upload(api_factory(detection_factory(0.2)), b"").status_code == 400


def test_oversized_upload_is_rejected(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """More bytes than the limit are a 413."""
    client = api_factory(detection_factory(0.2), max_image_bytes=TINY_BYTE_LIMIT)
    assert upload(client, make_png()).status_code == 413


def test_too_many_pixels_is_rejected(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """A tiny file that decodes to a large image is a 413."""
    client = api_factory(detection_factory(0.2), max_image_pixels=TINY_PIXEL_LIMIT)
    assert upload(client, make_png((20, 20))).status_code == 413


def test_missing_image_is_rejected(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """FastAPI's own validation answers 422 when the field is absent."""
    assert api_factory(detection_factory(0.2)).post("/inspections").status_code == 422


def test_detector_failure_returns_503(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """A model crash is reported as an unavailable service."""
    response = upload(api_factory(RuntimeError("model exploded")), make_png())
    assert response.status_code == 503
    assert response.json()["detail"] == "The detector could not analyse the image."
