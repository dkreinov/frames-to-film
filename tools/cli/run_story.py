"""Operator CLI — write the story.json for a project.

Usage:
    python tools/cli/run_story.py --project projects/{slug} \
           --arc-type life-montage \
           --subject "Olga, lifetime" \
           --tone nostalgic \
           --notes "Six photos spanning age 5 to 50"

Reads photos from {project}/inputs/, writes {project}/metadata/story.json
with the StoryDoc shape (arc_paragraph + pair_intents).

Falls back to project.json's stored brief if CLI args omitted.

Mock mode: set --mock to skip the LLM call (uses neutral placeholder
StoryDoc — useful for testing the pipeline shape).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.services.project_schema import (  # noqa: E402
    INPUTS_DIRNAME,
    METADATA_DIRNAME,
)
from backend.services.prompts import ORDER_FILENAME  # noqa: E402
from backend.services.story import StoryDoc, write_story  # noqa: E402

STORY_FILENAME = "story.json"
PROJECT_META_FILENAME = "project.json"


def _sort_key(filename: str) -> tuple[int, str]:
    """Match the project-wide convention (matches generate.py / orchestrator)."""
    import re
    base = filename.split(".")[0]
    m = re.match(r"^(\d+)(_([a-z]))?$", base)
    if m:
        return (int(m.group(1)), m.group(3) or "")
    return (9999, base)


def _discover_input_photos(project_dir: Path) -> list[Path]:
    """Ordered list of photos for story generation. Reads metadata/order.json
    if present (including loop duplicates); falls back to numeric sort."""
    inputs_dir = project_dir / INPUTS_DIRNAME
    if not inputs_dir.is_dir():
        raise FileNotFoundError(f"inputs/ missing: {inputs_dir}")
    valid_exts = {".jpg", ".jpeg", ".png"}
    order_path = project_dir / METADATA_DIRNAME / ORDER_FILENAME
    if order_path.is_file():
        try:
            order = json.loads(order_path.read_text()).get("order") or []
            existing = {p.name: p for p in inputs_dir.iterdir()
                        if p.is_file() and p.suffix.lower() in valid_exts}
            photos = [existing[name] for name in order if name in existing]
            if len(photos) >= 2:
                return photos
        except (json.JSONDecodeError, OSError):
            pass
    photos = sorted(
        {p for p in inputs_dir.iterdir()
         if p.is_file() and p.suffix.lower() in valid_exts},
        key=lambda p: _sort_key(p.name),
    )
    if len(photos) < 2:
        raise FileNotFoundError(
            f"need ≥2 photos in {inputs_dir}, got {len(photos)}"
        )
    return photos


def _load_project_meta(project_dir: Path) -> dict:
    p = project_dir / METADATA_DIRNAME / PROJECT_META_FILENAME
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _resolve_brief(args, meta: dict) -> dict:
    """CLI args override metadata fields."""
    return {
        "subject": args.subject or meta.get("subject", ""),
        "tone": args.tone or meta.get("tone", ""),
        "notes": args.notes or meta.get("notes", ""),
    }


def _mock_story(image_paths: list[Path], arc_type: str) -> StoryDoc:
    """Mock-mode StoryDoc — no LLM call. Used for pipeline shape tests."""
    n_pairs = len(image_paths) - 1
    return StoryDoc(
        arc_paragraph=f"[mock {arc_type} arc paragraph; {len(image_paths)} photos]",
        pair_intents=[
            {
                "from": i,
                "to": i + 1,
                "device": "cross_dissolve",
                "intent": f"[mock motion intent for pair {i}]",
            }
            for i in range(1, n_pairs + 1)
        ],
        arc_type=arc_type,
        reasoning="mock mode (no LLM call)",
        model_used="mock",
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Write story.json for a project.")
    p.add_argument("--project", required=True,
                   help="Path to project directory (e.g. projects/olga)")
    p.add_argument("--arc-type", required=True,
                   help="One of: life-montage, 3-act-heroic, travel-diary, "
                        "event-recap, day-in-life")
    p.add_argument("--subject", default=None, help="Brief subject")
    p.add_argument("--tone", default=None, help="Brief tone")
    p.add_argument("--notes", default=None, help="Brief notes")
    p.add_argument("--model", default=None, help="Override model (default qwen3-vl-plus)")
    p.add_argument("--mock", action="store_true",
                   help="Skip LLM call; write a placeholder StoryDoc.")
    args = p.parse_args()

    project_dir = Path(args.project).resolve()
    if not project_dir.is_dir():
        print(f"ERROR: project dir not found: {project_dir}", file=sys.stderr)
        return 1

    image_paths = _discover_input_photos(project_dir)
    meta = _load_project_meta(project_dir)
    brief = _resolve_brief(args, meta)

    if args.mock:
        doc = _mock_story(image_paths, args.arc_type)
    else:
        key = os.getenv("QWEEN_KEY", "")
        if not key:
            print("ERROR: QWEEN_KEY not in env (or use --mock)", file=sys.stderr)
            return 1
        kwargs = {
            "image_paths": image_paths,
            "brief": brief,
            "arc_type": args.arc_type,
            "key": key,
        }
        if args.model:
            kwargs["model"] = args.model
        doc = write_story(**kwargs)

    out_path = project_dir / METADATA_DIRNAME / STORY_FILENAME
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc.model_dump(), indent=2), encoding="utf-8")
    print(f"OK: wrote {out_path}")
    print(f"  arc_paragraph: {doc.arc_paragraph[:120]}...")
    print(f"  pair_intents:  {len(doc.pair_intents)}")
    print(f"  cost_usd:      ${doc.cost_usd:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
