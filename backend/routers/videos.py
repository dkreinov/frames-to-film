"""GET /projects/{id}/videos — list generated mp4 clips in pair order.

Videos land at <project>/kling_test/videos/seg_<a>_to_<b>.mp4 after
the Generate stage runs. This endpoint returns them in the sequence
implied by the frozen `_ordered_frames` helper (which honours
order.json when present, numeric sort otherwise) so the UI can line
up each pair thumbnail with its produced clip deterministically.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from backend.db import connect, init_db
from backend.deps import get_db_path, get_storage_root, get_user_id
from backend.services.generate import _ordered_frames

router = APIRouter(prefix="/projects/{project_id}/videos", tags=["videos"])


def _project_exists(db_path: Path, project_id: str, user_id: str) -> bool:
    with connect(db_path) as con:
        return con.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone() is not None


@router.get("")
def list_videos(
    project_id: str,
    db_path: Path = Depends(get_db_path),
    storage_root: Path = Depends(get_storage_root),
    user_id: str = Depends(get_user_id),
) -> dict:
    init_db(db_path)
    if not _project_exists(db_path, project_id, user_id):
        raise HTTPException(status_code=404, detail="project not found")

    project_dir = storage_root / user_id / project_id
    img_dir = project_dir / "kling_test"
    video_dir = img_dir / "videos"

    if not video_dir.is_dir() or not img_dir.is_dir():
        return {"videos": []}

    # Build expected pair sequence from ordered frames, then emit only
    # those that actually have an mp4 on disk.
    try:
        frames = _ordered_frames(img_dir, project_dir)
    except Exception:
        return {"videos": []}
    existing = {p.name for p in video_dir.glob("seg_*.mp4")}
    out: list[dict] = []
    for a, b in zip(frames, frames[1:]):
        pair_key = f"{a.stem}_to_{b.stem}"
        name = f"seg_{pair_key}.mp4"
        if name in existing:
            out.append({"name": name, "pair_key": pair_key})
    return {"videos": out}
