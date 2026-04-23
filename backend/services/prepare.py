"""Prepare stage service — 4:3 normalize.

Mock mode copies `tests/fixtures/fake_project/frame_*.png` → `<project>/outpainted/*.jpg`.
API mode delegates to `outpaint_images.run(src_dir, out_dir)`.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

from backend.db import REPO_ROOT

DEFAULT_FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "fake_project"


def get_fixture_root() -> Path:
    return DEFAULT_FIXTURE_ROOT


def run_prepare(project_dir: Path, mode: str, fixture_dir: Path | None = None) -> dict:
    project_dir = Path(project_dir)
    out_dir = project_dir / "outpainted"
    out_dir.mkdir(parents=True, exist_ok=True)

    if mode == "mock":
        src_fixture = Path(fixture_dir) if fixture_dir else DEFAULT_FIXTURE_ROOT
        frames = sorted(src_fixture.glob("frame_*_gemini.png"))
        if not frames:
            raise FileNotFoundError(f"no frame_*_gemini.png fixtures in {src_fixture}")
        for i, src in enumerate(frames, start=1):
            dst = out_dir / f"{i}.jpg"
            with Image.open(src) as im:
                im.convert("RGB").save(dst, "JPEG", quality=90)
        return {"produced": [p.name for p in sorted(out_dir.glob("*.jpg"))]}

    if mode == "api":
        from outpaint_images import run as outpaint_run  # imported lazily so tests don't need gemini key
        sources = project_dir / "sources"
        outpaint_run(src_dir=sources, out_dir=out_dir)
        return {"produced": [p.name for p in sorted(out_dir.glob("*.jpg"))]}

    raise ValueError(f"unknown mode: {mode}")


def prepare_runner(**payload) -> dict:
    return run_prepare(
        project_dir=Path(payload["project_dir"]),
        mode=payload["mode"],
        fixture_dir=Path(payload["fixture_dir"]) if payload.get("fixture_dir") else None,
    )
