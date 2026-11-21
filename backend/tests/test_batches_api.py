"""Tests for the /batches API routes."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_artifact_store, get_persona, get_repository
from app.core.persona import PersonaConfig
from app.main import app
from app.schemas import (
    Action,
    Assessment,
    InspectionReport,
    ReportContent,
    ReportSource,
    Severity,
    Verdict,
)
from app.services.repository import InspectionRecord, SqliteInspectionRepository
from app.services.storage import ArtifactStore
from tests.fakes import PERSONA_DATA

CREATED_AT = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)


def make_record(rec_id: str, batch_id: str, verdict: Verdict = Verdict.PASS) -> InspectionRecord:
    """Build a minimal inspection record."""
    assessment = Assessment(
        verdict=verdict,
        confidence=0.95,
        needs_review=False,
        severity=Severity.HIGH if verdict is Verdict.DEFECT else Severity.NONE,
        area_ratio=0.1 if verdict is Verdict.DEFECT else 0.0,
        action=Action.REJECT if verdict is Verdict.DEFECT else Action.ACCEPT,
        location=None,
    )
    content = ReportContent(
        summary="Summary",
        findings=["Finding"],
        recommendations=["Recommendation"],
        defect_type=None,
        voice_note_conflict=None,
    )
    report = InspectionReport(
        report_id=rec_id,
        generated_at=CREATED_AT,
        persona="factory_qc_operator",
        source=ReportSource.TEMPLATE,
        content=content,
        manual_review_notice=None,
    )
    return InspectionRecord(
        id=rec_id,
        created_at=CREATED_AT,
        persona="factory_qc_operator",
        batch_id=batch_id,
        category="bottle",
        score=0.9 if verdict is Verdict.DEFECT else 0.1,
        assessment=assessment,
        report=report,
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """Create a client wired to a clean SQLite database."""
    repo = SqliteInspectionRepository(tmp_path / "test.db")
    repo.initialize()
    store = ArtifactStore(tmp_path / "artifacts")
    persona = PersonaConfig.model_validate(PERSONA_DATA)
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_artifact_store] = lambda: store
    app.dependency_overrides[get_persona] = lambda: persona
    return TestClient(app)


def test_list_batches_and_get_batch(client: TestClient) -> None:
    """Listing batches returns summaries, and getting a batch returns its items."""
    repo = app.dependency_overrides[get_repository]()
    repo.add(make_record("1" * 32, "batch-1", Verdict.PASS))
    repo.add(make_record("2" * 32, "batch-1", Verdict.DEFECT))

    res = client.get("/batches")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["batch_id"] == "batch-1"
    assert data[0]["decision"] == "Rejected"
    assert data[0]["item_count"] == 2
    assert data[0]["defect_count"] == 1
    assert data[0]["pass_count"] == 1
    assert data[0]["review_count"] == 0
    assert data[0]["categories"] == ["bottle"]
    assert data[0]["last_inspection_at"].endswith("Z")

    res_detail = client.get("/batches/batch-1")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["summary"]["batch_id"] == "batch-1"
    assert len(detail["items"]) == 2


def test_get_batch_unknown_or_malformed_404(client: TestClient) -> None:
    """Unknown or malformed batch id returns 404."""
    assert client.get("/batches/nonexistent-batch").status_code == 404
    assert client.get("/batches/bad@id!").status_code == 404
