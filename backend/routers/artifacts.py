"""Artifact download endpoints.

- GET /projects/{id}/artifacts/{stage}/{name}
- GET /projects/{id}/download  (shortcut for full_movie.mp4)

Both enforce user scoping and protect against path traversal.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.db import connect, init_db
from backend.deps import get_db_path, get_storage_root, get_user_id

router = APIRouter(prefix="/projects/{project_id}", tags=["artifacts"])


def _project_exists(db_path: Path, project_id: str, user_id: str) -> bool:
    with connect(db_path) as con:
        return con.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone() is not None


def _resolve_safe(base: Path, *parts: str) -> Path:
    """Return base/parts resolved — raise HTTPException if the result
    escapes `base`. Guards against `..`, absolute paths, or URL-encoded
    traversals that slipped past FastAPI's path parser."""
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


@router.get("/artifacts/{stage}/{name:path}")
def stream_artifact(
    project_id: str,
    stage: str,
    name: str,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> FileResponse:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    project_dir = storage_root / user_id / project_id
    target = _resolve_safe(project_dir, stage, name)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(target)


@router.get("/download")
def download_full_movie(
    project_id: str,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> FileResponse:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    project_dir = storage_root / user_id / project_id
    target = project_dir / "kling_test" / "videos" / "full_movie.mp4"
    if not target.is_file():
        raise HTTPException(status_code=404, detail="full_movie.mp4 not found (run stitch?)")
    return FileResponse(target, media_type="video/mp4", filename="full_movie.mp4")
