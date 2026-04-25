"""Frame extraction helper for clip_judge.

Reuses the same ffmpeg-resolution pattern as `backend.services.generate`:
system PATH first, then bundled `tools/ffmpeg.exe` on Windows. Kept
self-contained so the judge module doesn't import from generate.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from backend.db import REPO_ROOT


def resolve_ffmpeg() -> str:
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    return str(REPO_ROOT / "tools" / "ffmpeg.exe")


_FFMPEG_BIN = resolve_ffmpeg()


def extract_frames_at_timestamps(
    video_path: Path,
    timestamps_s: list[float],
    output_dir: Path,
) -> list[Path]:
    """Extract a single frame at each timestamp; return jpg paths.

    Uses `-ss` before `-i` for fast seek, then `-vframes 1` for one frame.
    Frames written to `output_dir/frame_<ts:.1f>s.jpg`.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for ts in timestamps_s:
        dst = output_dir / f"frame_{ts:.1f}s.jpg"
        cmd = [
            _FFMPEG_BIN, "-y",
            "-ss", str(ts),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(dst),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        out.append(dst)
    return out
