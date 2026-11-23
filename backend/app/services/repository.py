"""SQLite persistence for inspection records, behind a small repository protocol."""

import logging
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel, Field

from app.schemas import (
    Action,
    Assessment,
    ImageUrls,
    InspectionReport,
    Severity,
    Verdict,
    VoiceNoteResult,
)
from app.services.storage import (
    INSPECTION_ID_PATTERN_TEXT,
    StorageError,
    validate_inspection_id,
)

logger = logging.getLogger(__name__)

DATABASE_TIMEOUT_SECONDS = 5.0
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.05
LOCKED_ERROR_FRAGMENT = "database is locked"
# Schema version is now managed by migration module
TIMESTAMP_PRECISION = "microseconds"
RECORD_NOT_FOUND_MESSAGE = "The inspection was not found."
CORRUPT_RECORD_MESSAGE = "A stored inspection record is corrupt."
STORAGE_UNAVAILABLE_MESSAGE = "The inspection store is unavailable."

T = TypeVar("T")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS inspections (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    persona TEXT NOT NULL,
    batch_id TEXT,
    category TEXT NOT NULL DEFAULT 'unknown',
    verdict TEXT NOT NULL,
    severity TEXT NOT NULL,
    action TEXT NOT NULL,
    confidence REAL NOT NULL,
    needs_review INTEGER NOT NULL,
    score REAL NOT NULL,
    area_ratio REAL NOT NULL,
    region TEXT,
    defect_type TEXT,
    report_pdf_path TEXT,
    record_json TEXT NOT NULL
)
"""
CREATE_CREATED_AT_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS inspections_created_at ON inspections (created_at DESC)"
)
CREATE_BATCH_ID_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS inspections_batch_id ON inspections (batch_id)"
)
CREATE_CATEGORY_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS inspections_category ON inspections (category)"
)
# SQLite does not accept a bound parameter in a PRAGMA, and the schema version is
# a fixed integer constant, so it is baked into this statement rather than user data.


INSERT_SQL = """
INSERT INTO inspections (
    id, created_at, persona, batch_id, category, verdict, severity, action,
    confidence, needs_review, score, area_ratio, region, defect_type, report_pdf_path, record_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
UPDATE_PDF_PATH_SQL = "UPDATE inspections SET report_pdf_path = ? WHERE id = ?"
SELECT_RECORD_SQL = "SELECT record_json, report_pdf_path FROM inspections WHERE id = ?"
SELECT_SUMMARIES_SQL = (
    "SELECT id, created_at, batch_id, report_pdf_path, record_json FROM inspections"
)
SELECT_BATCH_ITEMS_SQL = (
    "SELECT record_json, report_pdf_path FROM inspections "
    "WHERE batch_id = ? ORDER BY created_at ASC"
)
SELECT_BATCH_IDS_SQL = (
    "SELECT batch_id FROM inspections "
    "WHERE batch_id IS NOT NULL AND batch_id != '' "
    "GROUP BY batch_id ORDER BY MAX(created_at) DESC LIMIT ? OFFSET ?"
)
SELECT_EXPORT_SQL = """
SELECT record_json, report_pdf_path FROM inspections
"""
COUNT_SQL = "SELECT COUNT(*) FROM inspections"


class InspectionNotFoundError(RuntimeError):
    """Raised when an inspection id is malformed or unknown."""


class InspectionRecord(BaseModel):
    """One stored inspection, including the report and the batch it belongs to."""

    id: str = Field(pattern=INSPECTION_ID_PATTERN_TEXT)
    created_at: datetime
    persona: str
    batch_id: str | None = None
    category: str = "unknown"
    score: float = Field(ge=0)
    assessment: Assessment
    report: InspectionReport
    voice_note: VoiceNoteResult | None = None
    report_pdf_path: str | None = None


class InspectionSummary(BaseModel):
    """One history row, without the full report text."""

    id: str
    created_at: datetime
    category: str
    batch_id: str | None
    verdict: Verdict
    severity: Severity
    action: Action
    confidence: float = Field(ge=0, le=1)
    needs_review: bool
    thumbnail_url: str
    batch_decision: str | None = None
    report_pdf_available: bool = False
    report_pdf_url: str | None = None


class InspectionDetail(InspectionRecord):
    """One stored inspection plus its image URLs."""

    images: ImageUrls
    batch_decision: str | None = None
    report_pdf_available: bool = False
    report_pdf_url: str | None = None


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

    def set_report_pdf_path(self, inspection_id: str, name: str | None) -> None:
        """Update the report_pdf_path column for an inspection."""
        ...

    def items_in_batch(self, batch_id: str) -> list[InspectionRecord]:
        """Return all items belonging to a batch, ordered by creation time."""
        ...

    def list_batches(self, limit: int, offset: int) -> list[str]:
        """Return the newest batch IDs by last inspection time."""
        ...

    def list(
        self,
        limit: int,
        offset: int,
        batch_id: str | None = None,
        category: str | None = None,
    ) -> list[InspectionRecord]:
        """Return the newest records first, optionally filtered."""
        ...

    def count(self, batch_id: str | None = None, category: str | None = None) -> int:
        """Return how many records exist, optionally filtered."""
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
        """Create the table and indexes once at application startup.

        This now uses the migration module to ensure the schema is up‑to‑date.
        """
        from app.services.migration import initialize_schema

        self._run(lambda connection: initialize_schema(connection))

    def add(self, record: InspectionRecord) -> None:
        """Insert one validated record, keeping its JSON form for later reads."""
        validate_inspection_id(record.id)
        assessment = record.assessment
        location = assessment.location
        values = (
            record.id,
            _format_timestamp(record.created_at),
            record.persona,
            record.batch_id,
            record.category,
            assessment.verdict.value,
            assessment.severity.value,
            assessment.action.value,
            assessment.confidence,
            int(assessment.needs_review),
            record.score,
            assessment.area_ratio,
            location.region if location is not None else None,
            record.report.content.defect_type,
            record.report_pdf_path,
            record.model_dump_json(),
        )
        self._run(
            lambda connection: connection.execute(INSERT_SQL, values),
            write=True,
        )

    def set_report_pdf_path(self, inspection_id: str, name: str | None) -> None:
        """Set the report_pdf_path file name for an inspection."""
        validate_inspection_id(inspection_id)
        self._run(
            lambda connection: connection.execute(UPDATE_PDF_PATH_SQL, (name, inspection_id)),
            write=True,
        )

    def get(self, inspection_id: str) -> InspectionRecord | None:
        """Return one record, or None when the id is unknown."""
        validate_inspection_id(inspection_id)
        row = self._run(
            lambda connection: connection.execute(SELECT_RECORD_SQL, (inspection_id,)).fetchone()
        )
        if row is None:
            return None
        return _parse_record(row[0], row[1])

    def items_in_batch(self, batch_id: str) -> list[InspectionRecord]:
        """Return all items belonging to a batch, ordered by creation time."""
        rows = self._run(
            lambda connection: connection.execute(SELECT_BATCH_ITEMS_SQL, (batch_id,)).fetchall()
        )
        return [_parse_record(row[0], row[1]) for row in rows]

    def list_batches(self, limit: int, offset: int) -> list[str]:
        """Return newest unique batch ids."""
        rows = self._run(
            lambda connection: connection.execute(SELECT_BATCH_IDS_SQL, (limit, offset)).fetchall()
        )
        return [row[0] for row in rows]

    def list(
        self,
        limit: int,
        offset: int,
        batch_id: str | None = None,
        category: str | None = None,
    ) -> list[InspectionRecord]:
        """Return the newest records first, optionally filtered."""
        where, filters = _filters(batch_id, category)
        query = f"{SELECT_SUMMARIES_SQL}{where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        rows = self._run(
            lambda connection: connection.execute(query, (*filters, limit, offset)).fetchall()
        )
        return [_parse_record(row[4], row[3]) for row in rows]

    def count(self, batch_id: str | None = None, category: str | None = None) -> int:
        """Return how many records exist, optionally filtered."""
        where, filters = _filters(batch_id, category)
        row = self._run(
            lambda connection: connection.execute(f"{COUNT_SQL}{where}", filters).fetchone()
        )
        return int(row[0])

    def _run(self, operation: Callable[[sqlite3.Connection], T], *, write: bool = False) -> T:
        """Run one operation on a private connection, retrying brief locks."""
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                with self._connect(write=write) as connection:
                    return operation(connection)
            except sqlite3.OperationalError as exc:
                if attempt == RETRY_ATTEMPTS or not _is_locked(exc):
                    logger.exception("A SQLite operation failed")
                    raise StorageError(STORAGE_UNAVAILABLE_MESSAGE) from exc
                logger.warning(
                    "The SQLite database is locked; retrying (%d/%d).",
                    attempt,
                    RETRY_ATTEMPTS,
                )
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            except sqlite3.Error as exc:
                logger.exception("A SQLite operation failed")
                raise StorageError(STORAGE_UNAVAILABLE_MESSAGE) from exc
        raise AssertionError("unreachable")

    @contextmanager
    def _connect(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        """Open one connection for one operation, always closing it.

        A connection is never shared between threads. Writes take SQLite's write
        lock up front with ``BEGIN IMMEDIATE`` so competing writers queue on the
        busy timeout instead of failing a lock upgrade mid-transaction.
        """
        connection = sqlite3.connect(
            self._database_path,
            timeout=DATABASE_TIMEOUT_SECONDS,
            isolation_level=None if write else "DEFERRED",
        )
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.execute("COMMIT")
            else:
                connection.commit()
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()


def _is_locked(exc: sqlite3.OperationalError) -> bool:
    """Return True when SQLite reports that another connection holds the lock."""
    return LOCKED_ERROR_FRAGMENT in str(exc).lower()


def _filters(batch_id: str | None, category: str | None) -> tuple[str, list[str]]:
    """Return the optional WHERE clause and its bound string parameters."""
    clauses: list[str] = []
    params: list[str] = []
    if batch_id is not None:
        clauses.append("batch_id = ?")
        params.append(batch_id)
    if category is not None:
        clauses.append("category = ?")
        params.append(category)
    if not clauses:
        return "", params
    return " WHERE " + " AND ".join(clauses), params


def _parse_record(raw: str, report_pdf_path: str | None = None) -> InspectionRecord:
    """Re-validate one stored record and attach the current report_pdf_path."""
    try:
        record = InspectionRecord.model_validate_json(raw)
    except (ValueError, TypeError) as exc:
        logger.exception("A stored inspection record is corrupt")
        raise StorageError(CORRUPT_RECORD_MESSAGE) from exc
    if report_pdf_path is not None:
        record.report_pdf_path = report_pdf_path
    return record


def _format_timestamp(value: datetime) -> str:
    """Format a UTC timestamp so lexicographic order matches chronological order."""
    return value.isoformat(timespec=TIMESTAMP_PRECISION)
