"""Generate stage service — video pair synthesis.

Mock mode produces tiny ffmpeg 1s black-frame stubs (~50 KB each) so tests and
local E2E runs stay free. API mode calls fal.ai's Kling O3 first-last-frame
endpoint via backend.services.kling_fal — 5-second clips, audio off.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from backend.db import REPO_ROOT
from backend.services import kling_fal
from backend.services.judges import orchestrator as judges_orch
from backend.services.project_schema import (
    CLIPS_DIRNAME,
    CLIPS_RAW_DIRNAME,
    EXTENDED_DIRNAME,
    METADATA_DIRNAME,
    PROMPTS_DIRNAME,
)
from backend.services.prompts import ORDER_FILENAME, PROMPTS_FILENAME

# Default prompt used when a pair has no entry in prompts.json.
_FALLBACK_PROMPT = "Smooth cinematic transition between the two frames."

# Kling O3 5-second clips; matches the user-chosen duration in the plan.
_API_DURATION_S = 5


def _resolve_ffmpeg() -> str:
    """Pick the ffmpeg binary: system PATH first, then bundled Windows exe.

    Linux CI `apt-get install -y ffmpeg` puts it on PATH; Windows dev
    machines ship `tools/ffmpeg.exe` alongside the repo. Same precedence
    pattern as `concat_videos._get_ffmpeg_exe`.
    """
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    bundled = REPO_ROOT / "tools" / "ffmpeg.exe"
    return str(bundled)

FFMPEG_BIN = Path(_resolve_ffmpeg())


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


def _load_order(project_dir: Path) -> list[str] | None:
    """Return the user's saved Storyboard ordering (Phase 4 sub-plan 3),
    or None if no order.json has been written."""
    pj = project_dir / METADATA_DIRNAME / ORDER_FILENAME
    if not pj.is_file():
        return None
    try:
        data = json.loads(pj.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    raw = data.get("order")
    if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
        return raw
    return None


def _ordered_frames(img_dir: Path, project_dir: Path) -> list[Path]:
    """Sort frames in img_dir by the user's order.json if present, else by
    numeric filename. Filters to entries that actually exist on disk."""
    explicit = _load_order(project_dir)
    if explicit:
        existing = {p.name: p for p in img_dir.glob("*.jpg")}
        ordered = [existing[name] for name in explicit if name in existing]
        if ordered:
            return ordered
    return sorted(img_dir.glob("*.jpg"), key=lambda p: _sort_key(p.name))


def _load_prompts(project_dir: Path) -> dict[str, str]:
    """Return the {pair_key: prompt} map from <project>/prompts/prompts.json, or {}."""
    p = project_dir / PROMPTS_DIRNAME / PROMPTS_FILENAME
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    return {}


def run_generate(project_dir: Path, mode: str, fal_key: str | None = None) -> dict:
    project_dir = Path(project_dir)
    img_dir = project_dir / EXTENDED_DIRNAME
    video_dir = project_dir / CLIPS_DIRNAME / CLIPS_RAW_DIRNAME

    if not img_dir.is_dir():
        raise FileNotFoundError(f"extended dir missing (run extend first): {img_dir}")
    video_dir.mkdir(parents=True, exist_ok=True)

    if mode == "mock":
        frames = _ordered_frames(img_dir, project_dir)
        if len(frames) < 2:
            raise FileNotFoundError(f"need >=2 jpgs in {img_dir}, got {len(frames)}")
        produced: list[str] = []
        for a, b in zip(frames, frames[1:]):
            a_name = a.stem
            b_name = b.stem
            out = video_dir / f"seg_{a_name}_to_{b_name}.mp4"
            _make_stub(out)
            produced.append(out.name)
        # Mock mode skips judges — clips are placeholder black frames,
        # judging them wastes API spend and gives meaningless scores.
        return {"produced": produced}

    if mode == "api":
        if not fal_key:
            raise RuntimeError("fal_key missing from runner payload in api mode")
        frames = _ordered_frames(img_dir, project_dir)
        if len(frames) < 2:
            raise FileNotFoundError(f"need >=2 jpgs in {img_dir}, got {len(frames)}")
        prompts = _load_prompts(project_dir)
        produced = []
        for a, b in zip(frames, frames[1:]):
            pair_key = f"{a.stem}_to_{b.stem}"
            prompt = prompts.get(pair_key, _FALLBACK_PROMPT)
            mp4_bytes = kling_fal.generate_pair(
                a, b, prompt, fal_key=fal_key, duration=_API_DURATION_S
            )
            out = video_dir / f"seg_{pair_key}.mp4"
            out.write_bytes(mp4_bytes)
            produced.append(out.name)
        # Phase 7.1 — score every prompt + clip post-render (advisory).
        # Failure isolated: a judge error never fails the generate run.
        if judges_orch.is_enabled():
            try:
                judges_orch.run_post_generate_judges(project_dir)
            except Exception as exc:
                print(f"[judges] post-generate skipped: {exc!r}")
        return {"produced": produced}

    raise ValueError(f"unknown mode: {mode}")


def generate_runner(**payload) -> dict:
    return run_generate(
        project_dir=Path(payload["project_dir"]),
        mode=payload["mode"],
        fal_key=payload.get("fal_key"),
    )
