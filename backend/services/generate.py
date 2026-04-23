"""Generate stage service — video pair synthesis.

Mock mode produces tiny ffmpeg 1s black-frame stubs (~50 KB each) so tests and
local E2E runs stay free. API mode delegates to generate_all_videos.run.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from backend.db import REPO_ROOT

FFMPEG_BIN = REPO_ROOT / "tools" / "ffmpeg.exe"


def _sort_key(filename: str) -> tuple[int, str]:
    base = filename.split(".")[0]
    m = re.match(r"^(\d+)(_([a-z]))?$", base)
    if m:
        return (int(m.group(1)), m.group(3) or "")
    return (9999, base)


def _make_stub(dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(FFMPEG_BIN), "-y",
        "-f", "lavfi", "-i", "color=c=black:s=320x180:r=24:d=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "ultrafast", "-crf", "28",
        str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)


def run_generate(project_dir: Path, mode: str) -> dict:
    project_dir = Path(project_dir)
    img_dir = project_dir / "kling_test"
    video_dir = img_dir / "videos"

    if not img_dir.is_dir():
        raise FileNotFoundError(f"kling_test dir missing (run extend first): {img_dir}")
    video_dir.mkdir(parents=True, exist_ok=True)

    if mode == "mock":
        frames = sorted(img_dir.glob("*.jpg"), key=lambda p: _sort_key(p.name))
        if len(frames) < 2:
            raise FileNotFoundError(f"need >=2 jpgs in {img_dir}, got {len(frames)}")
        produced: list[str] = []
        for a, b in zip(frames, frames[1:]):
            a_name = a.stem
            b_name = b.stem
            out = video_dir / f"seg_{a_name}_to_{b_name}.mp4"
            _make_stub(out)
            produced.append(out.name)
        return {"produced": produced}

    if mode == "api":
        from generate_all_videos import run as generate_run
        generate_run(img_dir=img_dir, video_dir=video_dir)
        return {"produced": [p.name for p in sorted(video_dir.glob("seg_*.mp4"))]}

    raise ValueError(f"unknown mode: {mode}")


def generate_runner(**payload) -> dict:
    return run_generate(
        project_dir=Path(payload["project_dir"]),
        mode=payload["mode"],
    )
