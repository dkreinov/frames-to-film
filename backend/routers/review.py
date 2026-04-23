"""Review endpoint — mark a segment as winner/redo/bad."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.db import connect, init_db
from backend.deps import get_db_path, get_user_id

router = APIRouter(prefix="/projects/{project_id}/segments", tags=["review"])


@router.get("")
def list_segments(
    project_id: str,
    db_path: Path = Depends(get_db_path),
    user_id: str = Depends(get_user_id),
) -> dict:
    """List all reviewed segments for a project, sorted by seg_id.

    Returns `{segments: []}` if no reviews exist yet (200, not 404 —
    the absence of reviews is not an error). 404 only for unknown
    projects or projects owned by another user.
    """
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT seg_id, verdict, notes, updated_at FROM segments"
            " WHERE project_id = ? AND user_id = ?"
            " ORDER BY seg_id",
            (project_id, user_id),
        ).fetchall()
    return {"segments": [dict(r) for r in rows]}

ALLOWED_VERDICTS = {"winner", "redo", "bad"}


class ReviewRequest(BaseModel):
    verdict: str
    notes: str | None = None


def _project_exists(db_path: Path, project_id: str, user_id: str) -> bool:
    with connect(db_path) as con:
        return con.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone() is not None


@router.post("/{seg_id}/review")
def review_segment(
    project_id: str,
    seg_id: str,
    body: ReviewRequest,
    db_path: Path = Depends(get_db_path),
    user_id: str = Depends(get_user_id),
) -> dict:
    init_db(db_path)
    if body.verdict not in ALLOWED_VERDICTS:
        raise HTTPException(
            status_code=400,
            detail=f"verdict must be one of {sorted(ALLOWED_VERDICTS)}",
        )
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    now = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as con:
        con.execute(
            "INSERT INTO segments (project_id, user_id, seg_id, verdict, notes, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(project_id, seg_id) DO UPDATE SET"
            "   verdict = excluded.verdict,"
            "   notes = excluded.notes,"
            "   updated_at = excluded.updated_at",
            (project_id, user_id, seg_id, body.verdict, body.notes, now),
        )
    return {
        "project_id": project_id,
        "seg_id": seg_id,
        "verdict": body.verdict,
        "notes": body.notes,
        "updated_at": now,
    }
