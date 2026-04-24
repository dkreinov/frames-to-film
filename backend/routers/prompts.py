"""Prompts endpoints — auto-generate per-project prompts.json + read it back."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from backend.db import connect, init_db
from backend.deps import get_db_path, get_storage_root, get_user_id, resolve_gemini_key
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
    x_gemini_key: str | None = Header(default=None, alias="X-Gemini-Key"),
) -> dict:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    project_dir = storage_root / user_id / project_id
    payload: dict = {
        "project_dir": str(project_dir),
        "mode": body.mode,
        "style": body.style,
    }
    # Resolve + validate the Gemini key ONLY when api mode is requested.
    # Mock mode doesn't touch Gemini, so a missing key must not 400.
    if body.mode == "api":
        payload["gemini_key"] = resolve_gemini_key(x_gemini_key)
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


class PromptsPutBody(BaseModel):
    prompts: dict[str, str] = Field(min_length=1)

    @field_validator("prompts")
    @classmethod
    def all_values_non_empty(cls, v: dict[str, str]) -> dict[str, str]:
        for k, val in v.items():
            if not isinstance(val, str):
                raise ValueError(f"prompt for {k!r} is not a string")
        return v


@router.put("")
def put_prompts(
    project_id: str,
    body: PromptsPutBody,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> dict[str, str]:
    """Atomic full-file replace of <project>/prompts.json."""
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")
    if not body.prompts:
        raise HTTPException(status_code=400, detail="prompts map must not be empty")

    project_dir = storage_root / user_id / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    target = project_dir / "prompts.json"

    # Atomic write: tempfile in same dir + os.replace.
    fd, tmp_name = tempfile.mkstemp(prefix=".prompts-", suffix=".json", dir=project_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(body.prompts, f, indent=2)
        os.replace(tmp_name, target)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return body.prompts
