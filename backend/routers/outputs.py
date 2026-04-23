"""GET /projects/{id}/outputs/{stage} — list files in a stage dir.

Companion to artifacts.py's per-file stream endpoint. The Prepare
screen (Phase 4 sub-plan 2) calls this after the prepare job hits
`done`, then requests each listed name from /artifacts/outpainted/<name>.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from backend.db import connect, init_db
from backend.deps import get_db_path, get_storage_root, get_user_id

router = APIRouter(prefix="/projects/{project_id}/outputs", tags=["outputs"])


def _project_exists(db_path: Path, project_id: str, user_id: str) -> bool:
    with connect(db_path) as con:
        return con.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone() is not None


def _resolve_safe(base: Path, *parts: str) -> Path:
    base_resolved = base.resolve()
    try:
        target = (base / Path(*parts)).resolve()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"bad path: {exc}")
    try:
        target.relative_to(base_resolved)
    except ValueError:
        raise HTTPException(status_code=403, detail="path escape blocked")
    return target


@router.get("/{stage}")
def list_stage_outputs(
    project_id: str,
    stage: str,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> dict:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    project_dir = storage_root / user_id / project_id
    stage_dir = _resolve_safe(project_dir, stage)
    if not stage_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"stage dir not found: {stage}")
    # Sort for deterministic output; only regular files; no recursion
    outputs = sorted(p.name for p in stage_dir.iterdir() if p.is_file())
    return {"stage": stage, "outputs": outputs}
