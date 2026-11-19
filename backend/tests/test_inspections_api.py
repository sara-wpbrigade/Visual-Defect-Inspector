"""API tests for the inspection endpoints with a stubbed detector."""

import io
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from PIL import Image
from pydantic import SecretStr

from app.api.dependencies import get_detector, get_persona, get_report_service
from app.core.config import ReportWriterKind, Settings, get_settings
from app.core.persona import PersonaConfig
from app.main import app
from app.models.detector import Detection
from app.models.template_writer import TemplateReportWriter
from app.services.report import ReportService
from app.services.repository import SqliteInspectionRepository
from tests.fakes import StubDetector

PNG_CONTENT_TYPE = "image/png"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8"
TINY_BYTE_LIMIT = 20
TINY_PIXEL_LIMIT = 100
TEMPLATE_MAX_ATTEMPTS = 1
DEFAULT_MAX_TRANSCRIPT_CHARS = 1000
UNKNOWN_ID = "0" * 32
MALFORMED_ID = "../escape"

DetectionFactory = Callable[..., Detection]


def make_png(size: tuple[int, int] = (10, 10)) -> bytes:
    """Return a small valid PNG as bytes."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(180, 60, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


def upload(
    client: TestClient, data: bytes, name: str = "photo.png", batch_id: str | None = None
) -> Response:
    """Post image bytes to the inspection endpoint, optionally with a batch id."""
    files = {"image": (name, data, PNG_CONTENT_TYPE)}
    if batch_id is None:
        return client.post("/inspections", files=files)
    return client.post("/inspections", files=files, data={"batch_id": batch_id})


@pytest.fixture
def api_factory(tmp_path: Path, persona: PersonaConfig) -> Iterator[Callable[..., TestClient]]:
    """Build clients with the model, persona and settings under test control."""
    base = Settings(
        gemini_api_key=SecretStr("test-key"),
        gemini_model="test-model",
        upload_dir=tmp_path / "uploads",
        database_path=tmp_path / "inspections.db",
    )

    def build(result: Detection | Exception, **overrides: object) -> TestClient:
        settings = base.model_copy(update=dict(overrides))
        SqliteInspectionRepository(settings.database_path).initialize()
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_persona] = lambda: persona
        app.dependency_overrides[get_detector] = lambda: StubDetector(result)
        app.dependency_overrides[get_report_service] = lambda: ReportService(
            writer=TemplateReportWriter(),
            fallback_writer=TemplateReportWriter(),
            persona=persona,
            max_attempts=TEMPLATE_MAX_ATTEMPTS,
            max_transcript_chars=DEFAULT_MAX_TRANSCRIPT_CHARS,
        )
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
    assert body["assessment"]["location"] is None
    report = body["report"]
    assert report["report_id"] == body["inspection_id"]
    assert report["persona"] == "test_persona"
    assert report["source"] == "template"
    assert report["content"]["defect_type"] is None
    assert report["content"]["recommendations"] == ["Reject the item and remove it from the batch."]


def test_defect_location_is_returned(api_factory: Callable[..., TestClient]) -> None:
    """A two-dimensional mask gives the report a grid cell and a box."""
    mask = np.zeros((10, 10), dtype=bool)
    mask[0:2, 0:2] = True
    detection = Detection(score=0.9, anomaly_map=mask.astype(np.float32), mask=mask)
    body = upload(api_factory(detection), make_png()).json()
    location = body["assessment"]["location"]
    assert location["region"] == "upper left"
    assert location["bbox"] == [0.0, 0.0, 0.2, 0.2]


def test_pass_returns_accept(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """A clean photo comes back as a pass with an accept action."""
    response = upload(api_factory(detection_factory(0.2)), make_png())
    body = response.json()
    assert body["assessment"]["verdict"] == "pass"
    assert body["assessment"]["action"] == "accept"
    assert body["assessment"]["needs_review"] is False
    assert body["report"]["source"] == "template"
    assert body["report"]["content"]["defect_type"] is None
    assert body["report"]["content"]["recommendations"] == ["Accept the item; no action is needed."]


def test_template_report_runs_without_gemini_credentials(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """The template writer needs no Gemini key or model."""
    client = api_factory(
        detection_factory(0.2),
        report_writer=ReportWriterKind.TEMPLATE,
        gemini_api_key=None,
        gemini_model=None,
    )
    body = upload(client, make_png()).json()
    assert body["report"]["source"] == "template"


def test_artifacts_are_stored_under_the_inspection_id(
    api_factory: Callable[..., TestClient],
    detection_factory: DetectionFactory,
    tmp_path: Path,
) -> None:
    """The photo, overlay and thumbnail are written with fixed names."""
    response = upload(api_factory(detection_factory(0.2)), make_png())
    inspection_id = response.json()["inspection_id"]
    upload_dir = tmp_path / "uploads"
    assert sorted(path.name for path in upload_dir.glob(f"{inspection_id}*")) == [
        f"{inspection_id}.png",
        f"{inspection_id}_overlay.png",
        f"{inspection_id}_thumb.jpg",
    ]


def test_response_carries_created_at_batch_and_image_urls(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """A created inspection answers with its id, time, batch and image URLs."""
    body = upload(api_factory(detection_factory(0.2)), make_png(), batch_id="batch_1").json()
    inspection_id = body["inspection_id"]
    assert body["created_at"].endswith("Z")
    assert body["batch_id"] == "batch_1"
    assert body["images"] == {
        "photo": f"/inspections/{inspection_id}/photo",
        "overlay": f"/inspections/{inspection_id}/overlay",
        "thumbnail": f"/inspections/{inspection_id}/thumbnail",
    }


def test_batch_id_is_optional(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """A missing batch id is stored and returned as null."""
    body = upload(api_factory(detection_factory(0.2)), make_png()).json()
    assert body["batch_id"] is None


@pytest.mark.parametrize("batch_id", ["bad!id", "a" * 41])
def test_bad_batch_id_is_rejected(
    api_factory: Callable[..., TestClient],
    detection_factory: DetectionFactory,
    batch_id: str,
) -> None:
    """A batch id outside the pattern is a 422."""
    client = api_factory(detection_factory(0.2))
    assert upload(client, make_png(), batch_id=batch_id).status_code == 422


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


def test_history_and_detail_match_the_posted_inspection(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """The list and the detail endpoint return what the POST stored."""
    posted = upload(api_factory(detection_factory(0.9, 30)), make_png(), batch_id="batch_1").json()
    client = api_factory(detection_factory(0.2))
    history = client.get("/inspections").json()
    assert history["total"] == 1
    assert len(history["items"]) == 1
    summary = history["items"][0]
    assert summary["id"] == posted["inspection_id"]
    assert summary["batch_id"] == "batch_1"
    assert summary["verdict"] == "defect"
    assert summary["severity"] == "high"
    assert summary["action"] == "reject"
    assert summary["thumbnail_url"] == f"/inspections/{posted['inspection_id']}/thumbnail"
    detail = client.get(f"/inspections/{posted['inspection_id']}").json()
    assert detail["id"] == posted["inspection_id"]
    assert detail["batch_id"] == "batch_1"
    assert detail["score"] == posted["score"]
    assert detail["assessment"] == posted["assessment"]
    assert detail["report"]["report_id"] == posted["inspection_id"]
    assert detail["images"] == posted["images"]


def test_history_filters_by_batch_id(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """A batch query returns only that batch's inspections."""
    client = api_factory(detection_factory(0.2))
    upload(client, make_png(), batch_id="batch_1")
    upload(client, make_png(), batch_id="batch_1")
    upload(client, make_png(), batch_id="batch_2")
    filtered = client.get("/inspections", params={"batch_id": "batch_1"}).json()
    assert filtered["total"] == 2
    assert {item["batch_id"] for item in filtered["items"]} == {"batch_1"}
    assert client.get("/inspections").json()["total"] == 3


def test_history_pagination(
    api_factory: Callable[..., TestClient], detection_factory: DetectionFactory
) -> None:
    """Limit and offset page through the history."""
    client = api_factory(detection_factory(0.2))
    for _ in range(3):
        upload(client, make_png())
    page = client.get("/inspections", params={"limit": 2, "offset": 1}).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"limit": 0}, 422),
        ({"limit": 101}, 422),
        ({"offset": -1}, 422),
        ({"batch_id": "bad!id"}, 422),
    ],
)
def test_invalid_history_query_is_rejected(
    api_factory: Callable[..., TestClient],
    detection_factory: DetectionFactory,
    params: dict[str, str | int],
    status: int,
) -> None:
    """Out-of-range limits and a bad batch id are 422."""
    client = api_factory(detection_factory(0.2))
    assert client.get("/inspections", params=params).status_code == status


@pytest.mark.parametrize("kind", ["photo", "overlay", "thumbnail"])
def test_image_endpoints_return_images(
    api_factory: Callable[..., TestClient],
    detection_factory: DetectionFactory,
    kind: str,
) -> None:
    """Each image endpoint answers with the right media type and real bytes."""
    client = api_factory(detection_factory(0.9, 30))
    inspection_id = upload(client, make_png()).json()["inspection_id"]
    response = client.get(f"/inspections/{inspection_id}/{kind}")
    assert response.status_code == 200
    expected_type = "image/jpeg" if kind == "thumbnail" else "image/png"
    assert response.headers["content-type"].startswith(expected_type)
    magic = JPEG_MAGIC if kind == "thumbnail" else PNG_MAGIC
    assert response.content.startswith(magic)


@pytest.mark.parametrize("inspection_id", [UNKNOWN_ID, MALFORMED_ID])
def test_unknown_or_malformed_detail_is_404(
    api_factory: Callable[..., TestClient],
    detection_factory: DetectionFactory,
    inspection_id: str,
) -> None:
    """An unknown or malformed id cannot read a record."""
    client = api_factory(detection_factory(0.2))
    assert client.get(f"/inspections/{inspection_id}").status_code == 404


@pytest.mark.parametrize("kind", ["photo", "overlay", "thumbnail", "secret"])
def test_unknown_or_malformed_image_is_404(
    api_factory: Callable[..., TestClient],
    detection_factory: DetectionFactory,
    kind: str,
) -> None:
    """An unknown, malformed or missing image is a 404."""
    client = api_factory(detection_factory(0.2))
    upload(client, make_png())
    assert client.get(f"/inspections/{UNKNOWN_ID}/{kind}").status_code == 404
    assert client.get(f"/inspections/{MALFORMED_ID}/{kind}").status_code == 404


def test_record_survives_a_new_repository(
    api_factory: Callable[..., TestClient],
    detection_factory: DetectionFactory,
    tmp_path: Path,
) -> None:
    """The stored record is readable from the same database file again."""
    client = api_factory(detection_factory(0.9, 30))
    inspection_id = upload(client, make_png(), batch_id="batch_1").json()["inspection_id"]
    reopened = SqliteInspectionRepository(tmp_path / "inspections.db")
    record = reopened.get(inspection_id)
    assert record is not None
    assert record.batch_id == "batch_1"
    assert record.assessment.verdict.value == "defect"


def test_database_file_is_created(
    api_factory: Callable[..., TestClient],
    detection_factory: DetectionFactory,
    tmp_path: Path,
) -> None:
    """The SQLite database is written to the configured path."""
    upload(api_factory(detection_factory(0.2)), make_png())
    assert (tmp_path / "inspections.db").is_file()
