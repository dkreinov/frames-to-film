"""Job runner service — pending -> running -> done|error transitions.

For Phase 2 we use FastAPI BackgroundTasks + a synchronous runner function.
The synchronous runner is directly callable (bypassing BackgroundTasks) which
keeps tests deterministic without needing async polling.
"""
from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from backend.db import connect, init_db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(
    db_path: Path,
    *,
    project_id: str,
    user_id: str,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> str:
    init_db(db_path)
    job_id = uuid.uuid4().hex
    now = _now_iso()
    with connect(db_path) as con:
        con.execute(
            "INSERT INTO jobs (job_id, project_id, user_id, kind, status, payload, error, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'pending', ?, NULL, ?, ?)",
            (job_id, project_id, user_id, kind, json.dumps(payload or {}), now, now),
        )
    return job_id


def _set_status(db_path: Path, job_id: str, status: str, error: str | None = None) -> None:
    with connect(db_path) as con:
        con.execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE job_id = ?",
            (status, error, _now_iso(), job_id),
        )


def _load_payload(db_path: Path, job_id: str) -> dict[str, Any]:
    with connect(db_path) as con:
        row = con.execute("SELECT payload FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        raise KeyError(f"job not found: {job_id}")
    return json.loads(row["payload"] or "{}")


def run_job_sync(
    db_path: Path,
    job_id: str,
    runner: Callable[..., Any],
) -> None:
    """Execute `runner(**payload)` synchronously and record status transitions.

    Exceptions are swallowed and stored in the `error` column — the caller
    polls the jobs row to find out what happened.
    """
    _set_status(db_path, job_id, "running")
    try:
        payload = _load_payload(db_path, job_id)
        runner(**payload)
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        _set_status(db_path, job_id, "error", error=msg)
        return
    _set_status(db_path, job_id, "done")


def get_job(db_path: Path, project_id: str, user_id: str, job_id: str) -> dict[str, Any] | None:
    with connect(db_path) as con:
        row = con.execute(
            "SELECT job_id, project_id, user_id, kind, status, payload, error, created_at, updated_at"
            " FROM jobs WHERE job_id = ? AND project_id = ? AND user_id = ?",
            (job_id, project_id, user_id),
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["payload"] = json.loads(d.get("payload") or "{}")
    return d
