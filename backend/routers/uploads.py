"""Uploads router — multipart file upload + list + delete, user-scoped."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.db import connect, init_db
from backend.deps import get_db_path, get_storage_root, get_user_id
from backend.services.project_schema import INPUTS_DIRNAME

router = APIRouter(prefix="/projects/{project_id}/uploads", tags=["uploads"])

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}


class Upload(BaseModel):
    upload_id: str
    filename: str
    size_bytes: int
    created_at: str


def _project_exists(db_path: Path, project_id: str, user_id: str) -> bool:
    with connect(db_path) as con:
        row = con.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
    return row is not None


def _inputs_dir(storage_root: Path, user_id: str, project_id: str) -> Path:
    return storage_root / user_id / project_id / INPUTS_DIRNAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Upload)
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> Upload:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported content-type: {file.content_type}")
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing filename")

    dest_dir = _inputs_dir(storage_root, user_id, project_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / file.filename
    data = await file.read()
    dest.write_bytes(data)

    upload_id = uuid.uuid4().hex
    now = _now_iso()
    with connect(db_path) as con:
        con.execute(
            "INSERT INTO uploads (upload_id, project_id, user_id, filename, size_bytes, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (upload_id, project_id, user_id, file.filename, len(data), now),
        )
    return Upload(upload_id=upload_id, filename=file.filename, size_bytes=len(data), created_at=now)


@router.get("", response_model=list[Upload])
def list_uploads(
    project_id: str,
    db_path: Path = Depends(get_db_path),
    user_id: str = Depends(get_user_id),
) -> list[Upload]:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT upload_id, filename, size_bytes, created_at"
            " FROM uploads WHERE project_id = ? AND user_id = ? ORDER BY created_at",
            (project_id, user_id),
        ).fetchall()
    return [Upload(**dict(r)) for r in rows]


@router.delete("/{filename}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(
    project_id: str,
    filename: str,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> None:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    with connect(db_path) as con:
        cur = con.execute(
            "DELETE FROM uploads WHERE project_id = ? AND user_id = ? AND filename = ?",
            (project_id, user_id, filename),
        )
        deleted = cur.rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="upload not found")
    disk_path = _inputs_dir(storage_root, user_id, project_id) / filename
    if disk_path.exists():
        disk_path.unlink()
