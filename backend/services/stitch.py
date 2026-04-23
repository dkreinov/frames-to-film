"""Stitch stage service — ffmpeg stream-copy concat of segments.

No mode branch: stream-copy is free either way. The `mode` param is accepted
for signature symmetry with prepare/extend/generate but not used.
"""
from __future__ import annotations

from pathlib import Path


def run_stitch(project_dir: Path, mode: str | None = None) -> dict:
    project_dir = Path(project_dir)
    img_dir = project_dir / "kling_test"
    video_dir = img_dir / "videos"
    output_file = video_dir / "full_movie.mp4"

    if not video_dir.is_dir():
        raise FileNotFoundError(f"videos dir missing (run generate first): {video_dir}")
    segments = sorted(video_dir.glob("seg_*_to_*.mp4"))
    if not segments:
        raise RuntimeError(f"no segments to stitch in {video_dir}")

    from concat_videos import run as concat_run
    concat_run(img_dir=img_dir, video_dir=video_dir, output_file=output_file)

    return {"output_file": str(output_file), "segments": [s.name for s in segments]}


def stitch_runner(**payload) -> dict:
    return run_stitch(
        project_dir=Path(payload["project_dir"]),
        mode=payload.get("mode"),
    )
