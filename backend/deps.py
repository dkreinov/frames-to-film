"""Shared FastAPI dependencies — DB path, storage root, user id."""
from __future__ import annotations

from pathlib import Path

from fastapi import Header

from backend.db import DEFAULT_DB_PATH, REPO_ROOT

DEFAULT_STORAGE_ROOT = REPO_ROOT / "pipeline_runs"


def get_db_path() -> Path:
    return DEFAULT_DB_PATH


def get_storage_root() -> Path:
    return DEFAULT_STORAGE_ROOT


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    return (x_user_id or "local").strip() or "local"
