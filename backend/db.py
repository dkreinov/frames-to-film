"""SQLite index for the olga_movie backend.

One database file (`projects/index.db` by default) holds metadata rows:
projects, uploads, jobs, and segment verdicts. Large artifacts stay on disk
under `projects/<slug>/` (or `projects/<user_id>/<slug>/` in multi-user mode);
see `docs/PROJECT_SCHEMA.md` and `backend.services.project_schema`.

The schema is intentionally loose: TEXT IDs (UUID4) + JSON payload columns
so later phases can extend without migrations.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.services.project_schema import STORAGE_ROOT_DIRNAME

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / STORAGE_ROOT_DIRNAME / "index.db"


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS projects (
        project_id  TEXT PRIMARY KEY,
        user_id     TEXT NOT NULL,
        name        TEXT NOT NULL,
        config      TEXT NOT NULL DEFAULT '{}',
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS uploads (
        upload_id   TEXT PRIMARY KEY,
        project_id  TEXT NOT NULL,
        user_id     TEXT NOT NULL,
        filename    TEXT NOT NULL,
        size_bytes  INTEGER NOT NULL,
        created_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id      TEXT PRIMARY KEY,
        project_id  TEXT NOT NULL,
        user_id     TEXT NOT NULL,
        kind        TEXT NOT NULL,
        status      TEXT NOT NULL,
        payload     TEXT NOT NULL DEFAULT '{}',
        error       TEXT,
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS segments (
        project_id  TEXT NOT NULL,
        user_id     TEXT NOT NULL,
        seg_id      TEXT NOT NULL,
        verdict     TEXT NOT NULL,
        notes       TEXT,
        updated_at  TEXT NOT NULL,
        PRIMARY KEY (project_id, seg_id)
    )
    """,
)


def init_db(db_path: Path | str | None = None) -> Path:
    """Create the schema if it does not exist. Idempotent."""
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        for stmt in SCHEMA_STATEMENTS:
            con.execute(stmt)
        con.commit()
    return path


@contextmanager
def connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection with sensible defaults (Row factory + foreign keys)."""
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()
