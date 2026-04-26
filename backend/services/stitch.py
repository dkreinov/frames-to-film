"""Stitch stage service — ffmpeg stream-copy concat of segments.

No mode branch: stream-copy is free either way. The `mode` param is accepted
for signature symmetry with prepare/extend/generate but not used.
"""
from __future__ import annotations

from pathlib import Path

from backend.services.judges import orchestrator as judges_orch
from backend.services.project_schema import (
    CLIPS_DIRNAME,
    CLIPS_RAW_DIRNAME,
    EXTENDED_DIRNAME,
    FINAL_DIRNAME,
)


def run_stitch(project_dir: Path, mode: str | None = None) -> dict:
    project_dir = Path(project_dir)
    img_dir = project_dir / EXTENDED_DIRNAME
    video_dir = project_dir / CLIPS_DIRNAME / CLIPS_RAW_DIRNAME
    final_dir = project_dir / FINAL_DIRNAME
    final_dir.mkdir(parents=True, exist_ok=True)
    output_file = final_dir / "full_movie.mp4"

    if not video_dir.is_dir():
        raise FileNotFoundError(f"clips/raw dir missing (run generate first): {video_dir}")
    segments = sorted(video_dir.glob("seg_*_to_*.mp4"))
    if not segments:
        raise RuntimeError(f"no segments to stitch in {video_dir}")

    from concat_videos import run as concat_run
    concat_run(img_dir=img_dir, video_dir=video_dir, output_file=output_file)

    # Phase 7.1 — score the stitched movie post-stitch (advisory).
    # Mock mode produces black frames; judges still run if enabled but
    # the operator should treat scores as not meaningful in that mode.
    if mode != "mock" and judges_orch.is_enabled():
        try:
            judges_orch.run_post_stitch_judge(project_dir)
        except Exception as exc:
            print(f"[judges] post-stitch skipped: {exc!r}")

    return {"output_file": str(output_file), "segments": [s.name for s in segments]}


def stitch_runner(**payload) -> dict:
    return run_stitch(
        project_dir=Path(payload["project_dir"]),
        mode=payload.get("mode"),
    )
