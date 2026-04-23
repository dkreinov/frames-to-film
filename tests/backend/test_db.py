"""Step 3: SQLite schema contract (TDD red).

init_db(db_path) must create four tables: projects, uploads, jobs, segments.
Second call is a no-op (idempotent).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.db import init_db


EXPECTED_TABLES = {"projects", "uploads", "jobs", "segments"}


def _list_tables(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as con:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {row[0] for row in rows}


def test_init_db_creates_expected_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    init_db(db_path)
    assert _list_tables(db_path) >= EXPECTED_TABLES


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    init_db(db_path)
    first = _list_tables(db_path)
    init_db(db_path)  # second call must not raise
    second = _list_tables(db_path)
    assert first == second
