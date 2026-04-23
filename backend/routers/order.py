"""PUT/GET /projects/{id}/order — persist Storyboard frame ordering."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.db import connect, init_db
from backend.deps import get_db_path, get_storage_root, get_user_id

router = APIRouter(prefix="/projects/{project_id}/order", tags=["order"])


class OrderBody(BaseModel):
    order: list[str] = Field(min_length=0)


def _project_exists(db_path: Path, project_id: str, user_id: str) -> bool:
    with connect(db_path) as con:
        return con.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone() is not None


def _order_path(storage_root: Path, user_id: str, project_id: str) -> Path:
    return storage_root / user_id / project_id / "order.json"


@router.put("")
def put_order(
    project_id: str,
    body: OrderBody,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> dict:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    if len(body.order) == 0:
        raise HTTPException(status_code=400, detail="order must be non-empty")
    path = _order_path(storage_root, user_id, project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"order": body.order}, indent=2))
    return {"order": body.order}


@router.get("")
def get_order(
    project_id: str,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> dict:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    path = _order_path(storage_root, user_id, project_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="order.json not set")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"order.json unreadable: {exc}")
    return data
