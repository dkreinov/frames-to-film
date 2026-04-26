"""Operator CLI — write per-pair Kling prompts to prompts.json.

Usage:
    python tools/cli/run_prompts.py --project projects/{slug}

Reads {project}/metadata/story.json (must exist; run run_story.py first).
For each pair_intent in the story, calls prompt_writer.write_prompt()
with the matching extended/ image pair. Writes
{project}/prompts/prompts.json in the schema generate.py expects:
    {pair_key: prompt_string}

pair_key = "{img_a_stem}_to_{img_b_stem}".

Mock mode (--mock): writes a placeholder prompt per pair without
calling the LLM. Useful for pipeline shape validation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.services.project_schema import (  # noqa: E402
    EXTENDED_DIRNAME,
    METADATA_DIRNAME,
    PROMPTS_DIRNAME,
)
from backend.services.prompt_writer import write_prompt  # noqa: E402
from backend.services.prompts import PROMPTS_FILENAME  # noqa: E402

STORY_FILENAME = "story.json"


def _sort_key(filename: str) -> tuple[int, str]:
    base = filename.split(".")[0]
    m = re.match(r"^(\d+)(_([a-z]))?$", base)
    if m:
        return (int(m.group(1)), m.group(3) or "")
    return (9999, base)


def _load_story(project_dir: Path) -> dict:
    p = project_dir / METADATA_DIRNAME / STORY_FILENAME
    if not p.is_file():
        raise FileNotFoundError(
            f"story.json missing: {p}\nRun run_story.py first."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def _discover_extended_pairs(project_dir: Path) -> list[tuple[str, Path, Path]]:
    """List of (pair_key, image_a, image_b) tuples in render order.
    Mirrors generate.py / orchestrator pair-discovery logic."""
    img_dir = project_dir / EXTENDED_DIRNAME
    if not img_dir.is_dir():
        raise FileNotFoundError(
            f"extended/ missing: {img_dir}\nRun the extend stage first."
        )
    valid_exts = {".jpg", ".jpeg", ".png"}
    frames = sorted(
        {p for p in img_dir.iterdir()
         if p.is_file() and p.suffix.lower() in valid_exts},
        key=lambda p: _sort_key(p.name),
    )
    return [
        (f"{a.stem}_to_{b.stem}", a, b)
        for a, b in zip(frames, frames[1:])
    ]


def _mock_prompt(pair_intent: dict) -> str:
    """Mock-mode placeholder. Pipeline can still render mock-mode clips."""
    device = pair_intent.get("device", "cross_dissolve")
    intent = pair_intent.get("intent", "")
    return f"[mock] {device}: {intent}"


def main() -> int:
    p = argparse.ArgumentParser(description="Write per-pair Kling prompts.")
    p.add_argument("--project", required=True,
                   help="Path to project directory (e.g. projects/olga)")
    p.add_argument("--model", default=None,
                   help="Override model (default qwen3-vl-plus)")
    p.add_argument("--mock", action="store_true",
                   help="Skip LLM calls; write placeholder prompts.")
    args = p.parse_args()

    project_dir = Path(args.project).resolve()
    if not project_dir.is_dir():
        print(f"ERROR: project dir not found: {project_dir}", file=sys.stderr)
        return 1

    story = _load_story(project_dir)
    arc_type = story.get("arc_type") or "life-montage"
    pair_intents = story.get("pair_intents", [])
    if not pair_intents:
        print("ERROR: story.json has no pair_intents", file=sys.stderr)
        return 1

    pairs = _discover_extended_pairs(project_dir)
    if len(pairs) < len(pair_intents):
        print(
            f"WARN: extended/ has {len(pairs)} pairs but story.json has "
            f"{len(pair_intents)} pair_intents — using min.",
            file=sys.stderr,
        )

    n = min(len(pairs), len(pair_intents))
    prompts_out: dict[str, str] = {}

    if args.mock:
        for i in range(n):
            pair_key = pairs[i][0]
            prompts_out[pair_key] = _mock_prompt(pair_intents[i])
    else:
        key = os.getenv("QWEEN_KEY", "")
        if not key:
            print("ERROR: QWEEN_KEY not in env (or use --mock)", file=sys.stderr)
            return 1
        for i in range(n):
            pair_key, img_a, img_b = pairs[i]
            kwargs = {
                "image_a": img_a,
                "image_b": img_b,
                "pair_intent": pair_intents[i],
                "arc_type": arc_type,
                "key": key,
            }
            if args.model:
                kwargs["model"] = args.model
            prompts_out[pair_key] = write_prompt(**kwargs)
            print(f"  pair {pair_key}: {prompts_out[pair_key][:80]}...")

    out_dir = project_dir / PROMPTS_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / PROMPTS_FILENAME
    out_path.write_text(json.dumps(prompts_out, indent=2), encoding="utf-8")
    print(f"OK: wrote {out_path} ({len(prompts_out)} prompts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
