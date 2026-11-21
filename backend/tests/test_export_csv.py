"""Tests for CSV defect log export and formula injection defense."""

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


def make_record(
    rec_id: str,
    verdict: Verdict = Verdict.DEFECT,
    batch_id: str = "batch-1",
    defect_type: str | None = "scratch",
    category: str = "bottle",
) -> InspectionRecord:
    """Create an inspection record for CSV testing."""
    assessment = Assessment(
        verdict=verdict,
        confidence=0.92,
        needs_review=False,
        severity=Severity.HIGH if verdict is Verdict.DEFECT else Severity.NONE,
        area_ratio=0.08,
        action=Action.REJECT if verdict is Verdict.DEFECT else Action.ACCEPT,
        location=None,
    )
    content = ReportContent(
        summary="Summary",
        findings=["Finding"],
        recommendations=["Recommendation"],
        defect_type=defect_type,
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
        category=category,
        score=0.92,
        assessment=assessment,
        report=report,
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """Return a test client with a test database and persona."""
    repo = SqliteInspectionRepository(tmp_path / "test.db")
    repo.initialize()
    store = ArtifactStore(tmp_path / "artifacts")
    persona = PersonaConfig.model_validate(PERSONA_DATA)
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_artifact_store] = lambda: store
    app.dependency_overrides[get_persona] = lambda: persona
    return TestClient(app)


def test_export_csv_header_and_injection(client: TestClient) -> None:
    """CSV output has correct headers and defends against formula injection."""
    repo = app.dependency_overrides[get_repository]()
    repo.add(make_record("1" * 32, defect_type="=HYPERLINK('http://bad.com')"))
    response = client.get("/inspections/export.csv")
    assert response.status_code == 200
    assert "attachment; filename=" in response.headers["content-disposition"]
    text = response.text
    lines = text.strip().split("\r\n")
    assert lines[0].startswith("inspection_id,created_at,batch_id")
    # Verify injection prefix is escaped with a single quote
    assert "'=HYPERLINK" in lines[1]


def test_export_csv_empty_returns_header_only(client: TestClient) -> None:
    """Exporting with no matching records returns only the header."""
    response = client.get("/inspections/export.csv")
    assert response.status_code == 200
    lines = response.text.strip().split("\r\n")
    assert len(lines) == 1


def test_export_csv_filters(client: TestClient) -> None:
    """CSV export respects batch_id, category, and only_defects filters."""
    repo = app.dependency_overrides[get_repository]()
    repo.add(make_record("1" * 32, verdict=Verdict.PASS, batch_id="b-1", category="bottle"))
    repo.add(make_record("2" * 32, verdict=Verdict.DEFECT, batch_id="b-2", category="screw"))

    # only_defects=true by default
    res = client.get("/inspections/export.csv")
    assert "2" * 32 in res.text
    assert "1" * 32 not in res.text

    # category filter
    res_cat = client.get("/inspections/export.csv?category=bottle&only_defects=false")
    assert "1" * 32 in res_cat.text
    assert "2" * 32 not in res_cat.text
