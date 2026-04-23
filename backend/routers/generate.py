"""Generate stage endpoint — video-pair synthesis."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from backend.db import connect, init_db
from backend.deps import get_db_path, get_storage_root, get_user_id
from backend.services import generate as generate_svc
from backend.services import jobs as jobs_svc

router = APIRouter(prefix="/projects/{project_id}/generate", tags=["generate"])


class GenerateRequest(BaseModel):
    mode: str = "mock"


def _project_exists(db_path: Path, project_id: str, user_id: str) -> bool:
    with connect(db_path) as con:
        return con.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone() is not None


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def generate(
    project_id: str,
    body: GenerateRequest,
    bg: BackgroundTasks,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> dict:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    project_dir = storage_root / user_id / project_id
    payload = {"project_dir": str(project_dir), "mode": body.mode}
    job_id = jobs_svc.create_job(
        db_path, project_id=project_id, user_id=user_id, kind="generate", payload=payload
    )
    bg.add_task(jobs_svc.run_job_sync, db_path, job_id, generate_svc.generate_runner)
    return {"job_id": job_id}
