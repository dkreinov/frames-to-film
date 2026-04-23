"""Prompts endpoints — auto-generate per-project prompts.json + read it back."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from backend.db import connect, init_db
from backend.deps import get_db_path, get_storage_root, get_user_id
from backend.services import jobs as jobs_svc
from backend.services import prompts as prompts_svc

router = APIRouter(prefix="/projects/{project_id}/prompts", tags=["prompts"])


class PromptsGenerateRequest(BaseModel):
    mode: str = "mock"
    style: str = "cinematic"


def _project_exists(db_path: Path, project_id: str, user_id: str) -> bool:
    with connect(db_path) as con:
        return con.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone() is not None


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_prompts(
    project_id: str,
    body: PromptsGenerateRequest,
    bg: BackgroundTasks,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> dict:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    project_dir = storage_root / user_id / project_id
    payload = {
        "project_dir": str(project_dir),
        "mode": body.mode,
        "style": body.style,
    }
    job_id = jobs_svc.create_job(
        db_path, project_id=project_id, user_id=user_id, kind="prompts", payload=payload
    )
    bg.add_task(jobs_svc.run_job_sync, db_path, job_id, prompts_svc.prompts_runner)
    return {"job_id": job_id}


@router.get("")
def get_prompts(
    project_id: str,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> dict[str, str]:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    pj = storage_root / user_id / project_id / "prompts.json"
    if not pj.is_file():
        raise HTTPException(status_code=404, detail="prompts.json not generated yet")
    try:
        return json.loads(pj.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"prompts.json unreadable: {exc}")
