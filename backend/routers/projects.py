"""Projects CRUD router — user-scoped via X-User-ID header."""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.db import connect, init_db
from backend.deps import get_db_path, get_storage_root, get_user_id

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class Project(BaseModel):
    project_id: str
    user_id: str
    name: str
    created_at: str
    updated_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_dir(storage_root: Path, user_id: str, project_id: str) -> Path:
    return storage_root / user_id / project_id


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Project)
def create_project(
    body: ProjectCreate,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> Project:
    init_db(db_path)
    project_id = uuid.uuid4().hex
    now = _now_iso()
    with connect(db_path) as con:
        con.execute(
            "INSERT INTO projects (project_id, user_id, name, config, created_at, updated_at)"
            " VALUES (?, ?, ?, '{}', ?, ?)",
            (project_id, user_id, body.name, now, now),
        )
    _project_dir(storage_root, user_id, project_id).mkdir(parents=True, exist_ok=True)
    return Project(
        project_id=project_id,
        user_id=user_id,
        name=body.name,
        created_at=now,
        updated_at=now,
    )


@router.get("", response_model=list[Project])
def list_projects(
    db_path: Path = Depends(get_db_path),
    user_id: str = Depends(get_user_id),
) -> list[Project]:
    init_db(db_path)
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT project_id, user_id, name, created_at, updated_at"
            " FROM projects WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [Project(**dict(r)) for r in rows]


@router.get("/{project_id}", response_model=Project)
def get_project(
    project_id: str,
    db_path: Path = Depends(get_db_path),
    user_id: str = Depends(get_user_id),
) -> Project:
    init_db(db_path)
    with connect(db_path) as con:
        row = con.execute(
            "SELECT project_id, user_id, name, created_at, updated_at"
            " FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="project not found")
    return Project(**dict(row))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> None:
    init_db(db_path)
    with connect(db_path) as con:
        cur = con.execute(
            "DELETE FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        )
        deleted = cur.rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="project not found")
    proj_dir = _project_dir(storage_root, user_id, project_id)
    if proj_dir.exists():
        shutil.rmtree(proj_dir, ignore_errors=True)
