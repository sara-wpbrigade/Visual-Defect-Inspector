"""Tests for the SQLite inspection repository."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.schemas import (
    Action,
    Assessment,
    DefectLocation,
    InspectionReport,
    ReportContent,
    ReportSource,
    Severity,
    Verdict,
)
from app.services.repository import InspectionRecord, SqliteInspectionRepository, image_urls
from app.services.storage import StorageError

INSPECTION_ID = "0123456789abcdef0123456789abcdef"
OTHER_ID = "fedcba9876543210fedcba9876543210"
THIRD_ID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
HOSTILE_BATCH_ID = "'; DROP TABLE inspections; --"
BASE_TIME = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def make_report(inspection_id: str = INSPECTION_ID) -> InspectionReport:
    """Return a minimal valid report."""
    return InspectionReport(
        report_id=inspection_id,
        generated_at=BASE_TIME,
        persona="test_persona",
        source=ReportSource.TEMPLATE,
        content=ReportContent(
            summary="A defect was found.",
            findings=["The item needs attention."],
            recommendations=["Reject the item and remove it from the batch."],
            defect_type=None,
            voice_note_conflict=None,
        ),
    )


def make_record(
    inspection_id: str = INSPECTION_ID,
    created_at: datetime = BASE_TIME,
    batch_id: str | None = None,
    category: str = "unknown",
) -> InspectionRecord:
    """Return a valid record with overridable id, time, batch and category."""
    assessment = Assessment(
        verdict=Verdict.DEFECT,
        confidence=0.9,
        needs_review=False,
        severity=Severity.HIGH,
        area_ratio=0.2,
        action=Action.REJECT,
        location=DefectLocation(region="lower center", bbox=(0.2, 0.2, 0.8, 0.8)),
    )
    return InspectionRecord(
        id=inspection_id,
        created_at=created_at,
        persona="test_persona",
        batch_id=batch_id,
        category=category,
        score=0.9,
        assessment=assessment,
        report=make_report(inspection_id),
    )


@pytest.fixture
def repository(tmp_path: Path) -> SqliteInspectionRepository:
    """Return an initialized repository over a temporary database."""
    repo = SqliteInspectionRepository(tmp_path / "inspections.db")
    repo.initialize()
    return repo


def test_add_then_get_round_trips_equal(repository: SqliteInspectionRepository) -> None:
    """A stored record comes back with the same facts and report."""
    record = make_record()
    repository.add(record)
    assert repository.get(INSPECTION_ID) == record


def test_unknown_id_returns_none(repository: SqliteInspectionRepository) -> None:
    """An id that was never stored is absent, not an error."""
    assert repository.get(OTHER_ID) is None


def test_malformed_id_is_rejected(repository: SqliteInspectionRepository) -> None:
    """A malformed id never reaches the database."""
    with pytest.raises(StorageError):
        repository.get("../escape")


def test_initialize_is_idempotent(repository: SqliteInspectionRepository) -> None:
    """Creating the schema twice leaves one usable table."""
    repository.initialize()
    repository.add(make_record())
    assert repository.get(INSPECTION_ID) is not None


def test_list_is_newest_first(repository: SqliteInspectionRepository) -> None:
    """The history starts with the most recent inspection."""
    for inspection_id, hour in ((INSPECTION_ID, 1), (OTHER_ID, 2), (THIRD_ID, 3)):
        repository.add(make_record(inspection_id, datetime(2026, 1, 1, hour, 0, tzinfo=UTC)))
    assert [summary.id for summary in repository.list(limit=10, offset=0)] == [
        THIRD_ID,
        OTHER_ID,
        INSPECTION_ID,
    ]


def test_list_paginates(repository: SqliteInspectionRepository) -> None:
    """Limit and offset select one page of the newest-first list."""
    for inspection_id, hour in ((INSPECTION_ID, 1), (OTHER_ID, 2), (THIRD_ID, 3)):
        repository.add(make_record(inspection_id, datetime(2026, 1, 1, hour, 0, tzinfo=UTC)))
    page = repository.list(limit=1, offset=1)
    assert [summary.id for summary in page] == [OTHER_ID]


def test_list_filters_by_batch_id(repository: SqliteInspectionRepository) -> None:
    """A batch filter returns only that batch, newest first."""
    repository.add(make_record(INSPECTION_ID, BASE_TIME, batch_id="batch_1"))
    repository.add(
        make_record(OTHER_ID, datetime(2026, 1, 1, 13, 0, tzinfo=UTC), batch_id="batch_2")
    )
    repository.add(
        make_record(THIRD_ID, datetime(2026, 1, 1, 14, 0, tzinfo=UTC), batch_id="batch_1")
    )
    summaries = repository.list(limit=10, offset=0, batch_id="batch_1")
    assert [summary.id for summary in summaries] == [THIRD_ID, INSPECTION_ID]


def test_count_totals_and_filters(repository: SqliteInspectionRepository) -> None:
    """Count reports the total and the per-batch total."""
    repository.add(make_record(INSPECTION_ID, BASE_TIME, batch_id="batch_1"))
    repository.add(make_record(OTHER_ID, BASE_TIME, batch_id="batch_2"))
    assert repository.count() == 2
    assert repository.count(batch_id="batch_1") == 1
    assert repository.count(batch_id="missing") == 0


def test_summary_carries_the_history_fields(
    repository: SqliteInspectionRepository,
) -> None:
    """A summary exposes the verdict fields and the thumbnail URL."""
    repository.add(make_record(INSPECTION_ID, BASE_TIME, batch_id="batch_1"))
    summary = repository.list(limit=10, offset=0)[0]
    assert summary.verdict is Verdict.DEFECT
    assert summary.severity is Severity.HIGH
    assert summary.action is Action.REJECT
    assert summary.needs_review is False
    assert summary.batch_id == "batch_1"
    assert summary.thumbnail_url == image_urls(INSPECTION_ID).thumbnail


def test_hostile_values_are_kept_as_plain_data(
    repository: SqliteInspectionRepository, tmp_path: Path
) -> None:
    """A hostile batch id is bound as data and cannot damage the table."""
    record = make_record(INSPECTION_ID, BASE_TIME, batch_id=HOSTILE_BATCH_ID)
    repository.add(record)
    assert repository.get(INSPECTION_ID) == record
    connection = sqlite3.connect(tmp_path / "inspections.db")
    try:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'inspections'"
        ).fetchall()
    finally:
        connection.close()
    assert tables == [("inspections",)]


def test_corrupt_row_raises_storage_error(
    repository: SqliteInspectionRepository, tmp_path: Path
) -> None:
    """A row that is not valid record JSON becomes a domain error."""
    repository.add(make_record())
    connection = sqlite3.connect(tmp_path / "inspections.db")
    try:
        connection.execute(
            "UPDATE inspections SET record_json = ? WHERE id = ?",
            ("not json", INSPECTION_ID),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(StorageError):
        repository.get(INSPECTION_ID)


def test_summary_includes_the_category(repository: SqliteInspectionRepository) -> None:
    """A history row carries the category that produced it."""
    repository.add(make_record(INSPECTION_ID, BASE_TIME, category="widget"))
    assert repository.list(limit=10, offset=0)[0].category == "widget"


def test_list_filters_by_category(repository: SqliteInspectionRepository) -> None:
    """A category filter returns only that category's rows."""
    repository.add(make_record(INSPECTION_ID, BASE_TIME, category="widget"))
    repository.add(make_record(OTHER_ID, BASE_TIME, category="gadget"))
    summaries = repository.list(limit=10, offset=0, category="widget")
    assert [summary.id for summary in summaries] == [INSPECTION_ID]
    assert repository.count(category="widget") == 1
    assert repository.count(category="gadget") == 1


OLD_TABLE_SQL = """
CREATE TABLE inspections (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    persona TEXT NOT NULL,
    batch_id TEXT,
    verdict TEXT NOT NULL,
    severity TEXT NOT NULL,
    action TEXT NOT NULL,
    confidence REAL NOT NULL,
    needs_review INTEGER NOT NULL,
    score REAL NOT NULL,
    area_ratio REAL NOT NULL,
    region TEXT,
    defect_type TEXT,
    record_json TEXT NOT NULL
)
"""


def test_version_one_database_is_migrated(tmp_path: Path) -> None:
    """An older database gains the category column and old rows read as unknown."""
    database_path = tmp_path / "inspections.db"
    record = make_record()
    old_json = json.loads(record.model_dump_json())
    old_json.pop("category")
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(OLD_TABLE_SQL)
        connection.execute(
            "INSERT INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.created_at.isoformat(),
                record.persona,
                None,
                record.assessment.verdict.value,
                record.assessment.severity.value,
                record.assessment.action.value,
                record.assessment.confidence,
                0,
                record.score,
                record.assessment.area_ratio,
                None,
                None,
                json.dumps(old_json),
            ),
        )
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
    finally:
        connection.close()

    repository = SqliteInspectionRepository(database_path)
    repository.initialize()
    migrated = repository.get(INSPECTION_ID)
    assert migrated is not None
    assert migrated.category == "unknown"
    assert repository.list(limit=10, offset=0)[0].category == "unknown"
    connection = sqlite3.connect(database_path)
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        columns = connection.execute("PRAGMA table_info(inspections)").fetchall()
    finally:
        connection.close()
    assert version == 2
    assert "category" in {row[1] for row in columns}
