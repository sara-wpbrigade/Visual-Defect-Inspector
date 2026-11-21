"""Bring the inspections SQLite schema up to the latest version."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from app.services.repository import (
    CREATE_BATCH_ID_INDEX_SQL,
    CREATE_CATEGORY_INDEX_SQL,
    CREATE_CREATED_AT_INDEX_SQL,
    CREATE_TABLE_SQL,
)

LATEST_VERSION = 3


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Return whether *table* already has a column named *column*."""
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return any(row[1] == column for row in rows)


def _add_category(conn: sqlite3.Connection) -> None:
    """Add the category column, defaulting existing rows to ``unknown``."""
    if not _column_exists(conn, "inspections", "category"):
        conn.execute("ALTER TABLE inspections ADD COLUMN category TEXT NOT NULL DEFAULT 'unknown'")


def _add_report_pdf_path(conn: sqlite3.Connection) -> None:
    """Add the report_pdf_path column, defaulting existing rows to NULL."""
    if not _column_exists(conn, "inspections", "report_pdf_path"):
        conn.execute("ALTER TABLE inspections ADD COLUMN report_pdf_path TEXT NULL")


MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    2: _add_category,
    3: _add_report_pdf_path,
}


def initialize_schema(conn: sqlite3.Connection) -> None:
    """Create or upgrade the inspections table and its indexes.

    The work runs in one transaction. If a step fails the transaction is
    rolled back and the original database is left untouched.
    """
    try:
        conn.execute("BEGIN IMMEDIATE;")
        conn.execute(CREATE_TABLE_SQL)
        version = conn.execute("PRAGMA user_version;").fetchone()[0] or 0
        for target in sorted(MIGRATIONS):
            if version < target:
                MIGRATIONS[target](conn)
                version = target
        conn.execute(CREATE_CREATED_AT_INDEX_SQL)
        conn.execute(CREATE_BATCH_ID_INDEX_SQL)
        conn.execute(CREATE_CATEGORY_INDEX_SQL)
        conn.execute(f"PRAGMA user_version = {LATEST_VERSION};")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
