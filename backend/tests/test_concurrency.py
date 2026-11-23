"""Concurrency tests for simultaneous API inspections, lazy loading, and SQLite retries."""

from __future__ import annotations

import io
import sqlite3
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from app.api.dependencies import (
    get_category_catalog,
    get_category_verifier,
    get_detector_registry,
    get_persona,
    get_report_service,
)
from app.core.config import ReportWriterKind, Settings, get_settings
from app.core.persona import PersonaConfig
from app.main import app
from app.models.detector import Detection
from app.models.registry import DetectorRegistry
from app.models.template_writer import TemplateReportWriter
from app.schemas import (
    Action,
    Assessment,
    InspectionReport,
    ReportContent,
    ReportSource,
    Severity,
    Verdict,
)
from app.services import repository as repository_module
from app.services.category_verifier import CategoryVerifier
from app.services.report import ReportService
from app.services.repository import InspectionRecord, SqliteInspectionRepository
from app.services.storage import StorageError
from tests.fakes import (
    CATEGORY_ID,
    PERSONA_DATA,
    StubCategoryClassifier,
    StubDetectorRegistry,
    make_catalog,
    make_category_config,
)

CONCURRENT_REQUESTS = 12
BATCH_ID = "batch-concurrent"
CREATED_AT = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)


class ContentScoringDetector:
    """Stub detector that derives a deterministic score from pixel data and sleeps briefly."""

    def detect(self, image: Image.Image) -> Detection:
        """Compute a unique score from the red channel so cross-request mixing is obvious."""
        rgb = np.asarray(image.convert("RGB"))
        red = int(rgb[0, 0, 0])
        score = expected_score(red)
        time.sleep(0.02)
        height, width = rgb.shape[:2]
        mask = np.zeros((height, width), dtype=bool)
        anomaly_map = np.zeros((height, width), dtype=np.float32)
        if score >= 0.5:
            mask[0:2, 0:2] = True
            anomaly_map[0:2, 0:2] = score
        return Detection(score=score, anomaly_map=anomaly_map, mask=mask)


class LockedConnectionProxy:
    """Proxy a real SQLite connection and inject transient lock errors."""

    def __init__(self, real: sqlite3.Connection, should_fail: Callable[[], bool]) -> None:
        """Store the underlying SQLite connection and failure predicate."""
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_should_fail", should_fail)

    def execute(self, sql: str, parameters: Any = ()) -> sqlite3.Cursor:
        """Fail write starts/inserts when requested; delegate all other SQL."""
        upper = sql.lstrip().upper()
        if ("BEGIN IMMEDIATE" in upper or upper.startswith("INSERT")) and self._should_fail():
            raise sqlite3.OperationalError("database is locked")
        return self._real.execute(sql, parameters)

    def __getattr__(self, name: str) -> Any:
        """Forward attribute reads to the real connection."""
        return getattr(self._real, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Forward attribute writes to the real connection."""
        setattr(self._real, name, value)


def expected_score(red: int) -> float:
    """Return the deterministic score expected for a solid PNG with channel *red*."""
    return round(0.15 + (red / 255.0) * 0.75, 4)


def make_colored_png(red: int, size: tuple[int, int] = (10, 10)) -> bytes:
    """Encode a small lossless RGB PNG whose (0, 0) red pixel equals *red*."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(red, 60, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


def make_record(inspection_id: str) -> InspectionRecord:
    """Build a valid InspectionRecord for repository retry tests."""
    assessment = Assessment(
        verdict=Verdict.DEFECT,
        confidence=0.9,
        needs_review=False,
        severity=Severity.HIGH,
        area_ratio=0.1,
        action=Action.REJECT,
        location=None,
    )
    report = InspectionReport(
        report_id=inspection_id,
        generated_at=CREATED_AT,
        persona="factory_qc_operator",
        source=ReportSource.TEMPLATE,
        content=ReportContent(
            summary="Defect detected.",
            findings=["Defect found."],
            recommendations=["Reject the item."],
            defect_type=None,
            voice_note_conflict=None,
        ),
    )
    return InspectionRecord(
        id=inspection_id,
        created_at=CREATED_AT,
        persona="factory_qc_operator",
        batch_id=BATCH_ID,
        category=CATEGORY_ID,
        score=0.9,
        assessment=assessment,
        report=report,
    )


def test_concurrent_inspections_keep_scores_isolated_and_persist_all(tmp_path: Path) -> None:
    """Twelve simultaneous POST /inspections succeed with isolated scores and exact counts."""
    persona = PersonaConfig.model_validate(PERSONA_DATA)
    settings = Settings(
        gemini_api_key=SecretStr("test-key"),
        gemini_model="test-model",
        report_writer=ReportWriterKind.TEMPLATE,
        upload_dir=tmp_path / "uploads",
        database_path=tmp_path / "inspections.db",
    )
    SqliteInspectionRepository(settings.database_path).initialize()
    catalog = make_catalog(make_category_config())
    registry = StubDetectorRegistry(ContentScoringDetector(), catalog)
    classifier = StubCategoryClassifier(1.0)

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_category_catalog] = lambda: catalog
    app.dependency_overrides[get_persona] = lambda: persona
    app.dependency_overrides[get_detector_registry] = lambda: registry
    app.dependency_overrides[get_category_verifier] = lambda: CategoryVerifier(catalog, classifier)
    app.dependency_overrides[get_report_service] = lambda: ReportService(
        writer=TemplateReportWriter(),
        fallback_writer=TemplateReportWriter(),
        persona=persona,
        max_attempts=1,
        max_transcript_chars=1000,
    )

    reds = [index * 20 for index in range(CONCURRENT_REQUESTS)]
    try:
        with TestClient(app) as client:
            barrier = threading.Barrier(CONCURRENT_REQUESTS)

            def submit(index: int) -> tuple[int, int, dict[str, Any]]:
                png_bytes = make_colored_png(reds[index])
                barrier.wait(timeout=5.0)
                response = client.post(
                    "/inspections",
                    files={"image": (f"part_{index}.png", png_bytes, "image/png")},
                    data={"category": CATEGORY_ID, "batch_id": BATCH_ID},
                )
                return index, response.status_code, response.json()

            with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as pool:
                results = list(pool.map(submit, range(CONCURRENT_REQUESTS)))

            assert all(status == 201 for _, status, _ in results)
            ids = {body["inspection_id"] for _, _, body in results}
            assert len(ids) == CONCURRENT_REQUESTS
            for index, _, body in results:
                assert body["score"] == pytest.approx(expected_score(reds[index]))

            history = client.get("/inspections?limit=20&offset=0")
            assert history.status_code == 200
            history_body = history.json()
            assert history_body["total"] == CONCURRENT_REQUESTS
            assert len(history_body["items"]) == CONCURRENT_REQUESTS

            batch = client.get(f"/batches/{BATCH_ID}")
            assert batch.status_code == 200
            assert len(batch.json()["items"]) == CONCURRENT_REQUESTS

            csv_all = client.get(f"/inspections/export.csv?batch_id={BATCH_ID}&only_defects=false")
            assert csv_all.status_code == 200
            csv_lines = csv_all.text.strip().split("\r\n")
            assert len(csv_lines) - 1 == CONCURRENT_REQUESTS
    finally:
        app.dependency_overrides.clear()


def test_registry_loads_category_detector_once_under_concurrency() -> None:
    """Concurrent first requests for a category invoke the factory exactly once."""
    catalog = make_catalog(make_category_config())
    load_count = 0
    count_lock = threading.Lock()
    sentinel = ContentScoringDetector()

    def counting_factory(_checkpoint: str, _device: str) -> ContentScoringDetector:
        nonlocal load_count
        time.sleep(0.03)
        with count_lock:
            load_count += 1
        return sentinel

    registry = DetectorRegistry(catalog, "cpu", factory=counting_factory)
    barrier = threading.Barrier(CONCURRENT_REQUESTS)

    def fetch(_index: int) -> Any:
        barrier.wait(timeout=5.0)
        return registry.get(CATEGORY_ID)

    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as pool:
        detectors = list(pool.map(fetch, range(CONCURRENT_REQUESTS)))

    assert load_count == 1
    assert all(detector is sentinel for detector in detectors)


def test_repository_retries_database_locked_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Transient 'database is locked' errors are retried up to success."""
    db_path = tmp_path / "inspections.db"
    repo = SqliteInspectionRepository(db_path)
    repo.initialize()

    real_connect = sqlite3.connect
    remaining_failures = 2

    def flaky_connect(*args: Any, **kwargs: Any) -> Any:
        real_conn = real_connect(*args, **kwargs)
        failed_this_conn = False

        def should_fail() -> bool:
            nonlocal remaining_failures, failed_this_conn
            if not failed_this_conn and remaining_failures > 0:
                failed_this_conn = True
                remaining_failures -= 1
                return True
            return False

        return LockedConnectionProxy(real_conn, should_fail)

    monkeypatch.setattr(repository_module.sqlite3, "connect", flaky_connect)
    monkeypatch.setattr(repository_module.time, "sleep", lambda _seconds: None)

    record = make_record("a" * 32)
    repo.add(record)

    assert remaining_failures == 0
    assert repo.get("a" * 32) == record


def test_repository_raises_storage_error_after_exhausting_lock_retries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Persistent 'database is locked' errors raise StorageError after 3 attempts."""
    db_path = tmp_path / "inspections.db"
    repo = SqliteInspectionRepository(db_path)
    repo.initialize()

    real_connect = sqlite3.connect
    attempts = 0

    def always_locked_connect(*args: Any, **kwargs: Any) -> Any:
        real_conn = real_connect(*args, **kwargs)
        failed_this_conn = False

        def should_fail() -> bool:
            nonlocal attempts, failed_this_conn
            if not failed_this_conn:
                failed_this_conn = True
                attempts += 1
                return True
            return False

        return LockedConnectionProxy(real_conn, should_fail)

    monkeypatch.setattr(repository_module.sqlite3, "connect", always_locked_connect)
    monkeypatch.setattr(repository_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(StorageError):
        repo.add(make_record("b" * 32))

    assert attempts == repository_module.RETRY_ATTEMPTS
