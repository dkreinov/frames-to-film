"""Job polling endpoint."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from backend.db import init_db
from backend.deps import get_db_path, get_user_id
from backend.services import jobs as jobs_svc

router = APIRouter(prefix="/projects/{project_id}/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job_status(
    project_id: str,
    job_id: str,
    db_path: Path = Depends(get_db_path),
    user_id: str = Depends(get_user_id),
) -> dict:
    init_db(db_path)
    job = jobs_svc.get_job(db_path, project_id=project_id, user_id=user_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job
