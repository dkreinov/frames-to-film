"""Extend stage service — 4:3 outpainted → 16:9 kling_test frames.

Mock mode copies outpainted/*.jpg → kling_test/*.jpg.
API mode is not wired to a productized path as of Phase 6 — the
original legacy outpaint-16-9 script lives at
`legacy/scripts/outpaint_16_9.py` but is not imported here (Settings
UI keeps extend→api disabled).
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
        # Phase-1 outpaint_16_9.py moved to legacy/scripts/. See prepare.py
        # for the same pattern — Settings UI gates extend→api disabled.
        raise NotImplementedError(
            "extend api mode is not productized in Phase 6 — "
            "flip Settings→Storyboard extend to mock, or run "
            "legacy/scripts/outpaint_16_9.py directly."
        )

    raise ValueError(f"unknown mode: {mode}")


def extend_runner(**payload) -> dict:
    return run_extend(
        project_dir=Path(payload["project_dir"]),
        mode=payload["mode"],
    )
