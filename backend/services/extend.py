"""Extend stage service — 4:3 outpainted → 16:9 kling_test frames.

Mock mode copies outpainted/*.jpg → kling_test/*.jpg.
API mode delegates to `outpaint_16_9.run(src_dir, out_dir)`.
"""
from __future__ import annotations

import shutil
from pathlib import Path


def run_extend(project_dir: Path, mode: str) -> dict:
    project_dir = Path(project_dir)
    src_dir = project_dir / "outpainted"
    out_dir = project_dir / "kling_test"
    out_dir.mkdir(parents=True, exist_ok=True)

    if mode == "mock":
        if not src_dir.is_dir():
            raise FileNotFoundError(f"outpainted dir missing (run prepare first): {src_dir}")
        frames = sorted(src_dir.glob("*.jpg"))
        if not frames:
            raise FileNotFoundError(f"no jpgs in {src_dir}")
        for src in frames:
            shutil.copy2(src, out_dir / src.name)
        return {"produced": [p.name for p in sorted(out_dir.glob("*.jpg"))]}

    if mode == "api":
        from outpaint_16_9 import run as extend_run
        extend_run(src_dir=src_dir, out_dir=out_dir)
        return {"produced": [p.name for p in sorted(out_dir.glob("*.jpg"))]}

    raise ValueError(f"unknown mode: {mode}")


def extend_runner(**payload) -> dict:
    return run_extend(
        project_dir=Path(payload["project_dir"]),
        mode=payload["mode"],
    )
