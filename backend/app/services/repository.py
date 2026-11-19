"""SQLite persistence for inspection records, behind a small repository protocol."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from app.schemas import (
    Action,
    Assessment,
    ImageUrls,
    InspectionReport,
    Severity,
    Verdict,
)
from app.services.storage import (
    INSPECTION_ID_PATTERN_TEXT,
    StorageError,
    validate_inspection_id,
)

logger = logging.getLogger(__name__)

DATABASE_TIMEOUT_SECONDS = 5.0
SCHEMA_VERSION = 1
TIMESTAMP_PRECISION = "microseconds"
RECORD_NOT_FOUND_MESSAGE = "The inspection was not found."
CORRUPT_RECORD_MESSAGE = "A stored inspection record is corrupt."
STORAGE_UNAVAILABLE_MESSAGE = "The inspection store is unavailable."

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS inspections (
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
CREATE_CREATED_AT_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS inspections_created_at ON inspections (created_at DESC)"
)
CREATE_BATCH_ID_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS inspections_batch_id ON inspections (batch_id)"
)
# SQLite does not accept a bound parameter in a PRAGMA, and the schema version is
# a fixed integer constant, so it is baked into this statement rather than user data.
SET_USER_VERSION_SQL = f"PRAGMA user_version = {SCHEMA_VERSION}"

INSERT_SQL = """
INSERT INTO inspections (
    id, created_at, persona, batch_id, verdict, severity, action,
    confidence, needs_review, score, area_ratio, region, defect_type, record_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
SELECT_RECORD_SQL = "SELECT record_json FROM inspections WHERE id = ?"
SELECT_SUMMARIES_SQL = (
    "SELECT id, created_at, batch_id, record_json FROM inspections "
    "ORDER BY created_at DESC LIMIT ? OFFSET ?"
)
SELECT_BATCH_SUMMARIES_SQL = (
    "SELECT id, created_at, batch_id, record_json FROM inspections "
    "WHERE batch_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
)
COUNT_SQL = "SELECT COUNT(*) FROM inspections"
COUNT_BATCH_SQL = "SELECT COUNT(*) FROM inspections WHERE batch_id = ?"


class InspectionNotFoundError(RuntimeError):
    """Raised when an inspection id is malformed or unknown."""


class InspectionRecord(BaseModel):
    """One stored inspection, including the report and the batch it belongs to."""

    id: str = Field(pattern=INSPECTION_ID_PATTERN_TEXT)
    created_at: datetime
    persona: str
    batch_id: str | None = None
    score: float = Field(ge=0)
    assessment: Assessment
    report: InspectionReport


class InspectionSummary(BaseModel):
    """One history row, without the full report text."""

    id: str
    created_at: datetime
    batch_id: str | None
    verdict: Verdict
    severity: Severity
    action: Action
    confidence: float = Field(ge=0, le=1)
    needs_review: bool
    thumbnail_url: str


class InspectionDetail(InspectionRecord):
    """One stored inspection plus its image URLs."""

    images: ImageUrls


class InspectionHistory(BaseModel):
    """One page of the inspection history plus the total number of records."""

    items: list[InspectionSummary]
    total: int


class InspectionRepository(Protocol):
    """The persistence operations the API needs."""

    def add(self, record: InspectionRecord) -> None:
        """Insert one validated record."""
        ...

    def get(self, inspection_id: str) -> InspectionRecord | None:
        """Return one record, or None when the id is unknown."""
        ...

    def list(self, limit: int, offset: int, batch_id: str | None = None) -> list[InspectionSummary]:
        """Return the newest summaries first, optionally for one batch."""
        ...

    def count(self, batch_id: str | None = None) -> int:
        """Return how many records exist, optionally for one batch."""
        ...


def image_urls(inspection_id: str) -> ImageUrls:
    """Return the relative URLs of the three stored images."""
    return ImageUrls(
        photo=f"/inspections/{inspection_id}/photo",
        overlay=f"/inspections/{inspection_id}/overlay",
        thumbnail=f"/inspections/{inspection_id}/thumbnail",
    )


class SqliteInspectionRepository:
    """Store inspection records in one SQLite database file."""

    def __init__(self, database_path: Path) -> None:
        """Remember the database file to open for every operation."""
        self._database_path = database_path

    def initialize(self) -> None:
        """Create the table and indexes once at application startup."""
        with self._connect() as connection:
            connection.execute(CREATE_TABLE_SQL)
            connection.execute(CREATE_CREATED_AT_INDEX_SQL)
            connection.execute(CREATE_BATCH_ID_INDEX_SQL)
            connection.execute(SET_USER_VERSION_SQL)

    def add(self, record: InspectionRecord) -> None:
        """Insert one validated record, keeping its JSON form for later reads."""
        validate_inspection_id(record.id)
        assessment = record.assessment
        location = assessment.location
        with self._connect() as connection:
            connection.execute(
                INSERT_SQL,
                (
                    record.id,
                    _format_timestamp(record.created_at),
                    record.persona,
                    record.batch_id,
                    assessment.verdict.value,
                    assessment.severity.value,
                    assessment.action.value,
                    assessment.confidence,
                    int(assessment.needs_review),
                    record.score,
                    assessment.area_ratio,
                    location.region if location is not None else None,
                    record.report.content.defect_type,
                    record.model_dump_json(),
                ),
            )

    def get(self, inspection_id: str) -> InspectionRecord | None:
        """Return one record, or None when the id is unknown."""
        validate_inspection_id(inspection_id)
        with self._connect() as connection:
            row = connection.execute(SELECT_RECORD_SQL, (inspection_id,)).fetchone()
        if row is None:
            return None
        return _parse_record(row[0])

    def list(self, limit: int, offset: int, batch_id: str | None = None) -> list[InspectionSummary]:
        """Return the newest summaries first, optionally for one batch."""
        query, params = _summary_query(batch_id, limit, offset)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_summary(_parse_record(row[3])) for row in rows]

    def count(self, batch_id: str | None = None) -> int:
        """Return how many records exist, optionally for one batch."""
        query, params = (COUNT_BATCH_SQL, (batch_id,)) if batch_id else (COUNT_SQL, ())
        with self._connect() as connection:
            row = connection.execute(query, params).fetchone()
        return int(row[0])

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open one connection for one operation, always closing it."""
        connection = sqlite3.connect(self._database_path, timeout=DATABASE_TIMEOUT_SECONDS)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            logger.exception("A SQLite operation failed")
            raise StorageError(STORAGE_UNAVAILABLE_MESSAGE) from exc
        finally:
            connection.close()


def _summary_query(
    batch_id: str | None, limit: int, offset: int
) -> tuple[str, tuple[str, int, int] | tuple[int, int]]:
    """Return the listing query and its bound parameters."""
    if batch_id is None:
        return SELECT_SUMMARIES_SQL, (limit, offset)
    return SELECT_BATCH_SUMMARIES_SQL, (batch_id, limit, offset)


def _summary(record: InspectionRecord) -> InspectionSummary:
    """Project one stored record into a history row."""
    assessment = record.assessment
    return InspectionSummary(
        id=record.id,
        created_at=record.created_at,
        batch_id=record.batch_id,
        verdict=assessment.verdict,
        severity=assessment.severity,
        action=assessment.action,
        confidence=assessment.confidence,
        needs_review=assessment.needs_review,
        thumbnail_url=image_urls(record.id).thumbnail,
    )


def _parse_record(record_json: str) -> InspectionRecord:
    """Re-validate one stored record, turning corruption into a domain error."""
    try:
        return InspectionRecord.model_validate_json(record_json)
    except (ValueError, TypeError) as exc:
        logger.exception("A stored inspection record is corrupt")
        raise StorageError(CORRUPT_RECORD_MESSAGE) from exc


def _format_timestamp(value: datetime) -> str:
    """Format a UTC timestamp so lexicographic order matches chronological order."""
    return value.isoformat(timespec=TIMESTAMP_PRECISION)
