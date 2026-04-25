"""Judge orchestrator — wires the three judges into the pipeline.

Public API:
- `is_enabled()` — read the JUDGES_ENABLED env flag with auto-detect.
- `run_post_generate_judges(project_dir)` — score all prompts + all
  rendered clips for a project; persist to run.json.
- `run_post_stitch_judge(project_dir, ...)` — score the assembled movie;
  persist to run.json.
- `read_run_json(project_dir)` / `write_run_json(project_dir, data)` —
  thin helpers around the per-project run.json file.

run.json shape (mirrors phase_7_flow.md § contracts):
{
  "project_id": "...",
  "created_at": "ISO 8601",
  "stages": {
    "generate": {"status": "done", "produced": [...]},
    "stitch":   {"status": "done", "output_file": "..."},
    ...
  },
  "judges": {
    "prompt": [JudgeScore, ...],   # 1 per pair
    "clip":   [JudgeScore, ...],   # 1 per pair
    "movie":  JudgeScore | null    # 1 per project
  },
  "cost_usd_total": 0.0,
  "reroll_count": 0
}

Failure mode: if any judge call raises, log + continue. Judges are a
quality LAYER, not a correctness requirement; the pipeline must still
produce mp4s when judges fail or keys are missing.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.judges import score_clip, score_movie, score_prompt

RUN_JSON_NAME = "run.json"


# --- env flag ---------------------------------------------------------

def is_enabled() -> bool:
    """JUDGES_ENABLED=on|off|auto. Default auto: on iff keys present."""
    flag = (os.getenv("JUDGES_ENABLED") or "auto").strip().lower()
    if flag == "on":
        return True
    if flag == "off":
        return False
    # auto
    return bool(os.getenv("gemini"))  # at minimum need Gemini for prompt+clip


# --- run.json helpers -------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_run_json(project_dir: Path) -> dict[str, Any]:
    p = Path(project_dir) / RUN_JSON_NAME
    if not p.is_file():
        return {
            "project_id": Path(project_dir).name,
            "created_at": _now_iso(),
            "stages": {},
            "judges": {"prompt": [], "clip": [], "movie": None},
            "cost_usd_total": 0.0,
            "reroll_count": 0,
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Don't blow up on corrupt run.json — start fresh, log once.
        return {
            "project_id": Path(project_dir).name,
            "created_at": _now_iso(),
            "stages": {},
            "judges": {"prompt": [], "clip": [], "movie": None},
            "cost_usd_total": 0.0,
            "reroll_count": 0,
        }


def write_run_json(project_dir: Path, data: dict[str, Any]) -> None:
    p = Path(project_dir) / RUN_JSON_NAME
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _recompute_cost(data: dict[str, Any]) -> float:
    total = 0.0
    for entry in data["judges"].get("prompt", []) or []:
        total += float(entry.get("cost_usd", 0) or 0)
    for entry in data["judges"].get("clip", []) or []:
        total += float(entry.get("cost_usd", 0) or 0)
    movie = data["judges"].get("movie")
    if movie:
        total += float(movie.get("cost_usd", 0) or 0)
    return round(total, 6)


# --- pair / clip discovery -------------------------------------------

def _sort_key(filename: str) -> tuple[int, str]:
    base = filename.split(".")[0]
    m = re.match(r"^(\d+)(_([a-z]))?$", base)
    if m:
        return (int(m.group(1)), m.group(3) or "")
    return (9999, base)


def _discover_pairs(project_dir: Path) -> list[tuple[str, Path, Path]]:
    """Return [(pair_key, image_a_path, image_b_path)] in render order."""
    img_dir = project_dir / "kling_test"
    if not img_dir.is_dir():
        return []
    frames = sorted(img_dir.glob("*.jpg"), key=lambda p: _sort_key(p.name))
    return [
        (f"{a.stem}_to_{b.stem}", a, b)
        for a, b in zip(frames, frames[1:])
    ]


def _load_prompts(project_dir: Path) -> dict[str, str]:
    p = project_dir / "prompts.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    except (json.JSONDecodeError, OSError):
        return {}


# --- post-generate judges --------------------------------------------

def run_post_generate_judges(
    project_dir: Path,
    gemini_key: str | None = None,
    *,
    skip_prompt: bool = False,
    skip_clip: bool = False,
) -> dict[str, Any]:
    """Score every (prompt, image_a, image_b) tuple AND every rendered
    clip. Persists to run.json. Returns the updated dict.

    Idempotent: re-running overwrites previous prompt/clip judge entries.
    """
    project_dir = Path(project_dir)
    if gemini_key is None:
        gemini_key = os.getenv("gemini") or ""

    data = read_run_json(project_dir)
    data["stages"].setdefault("generate", {})
    data["judges"]["prompt"] = []
    data["judges"]["clip"] = []

    if not gemini_key:
        # No key → log neutral fallback & bail. Judges still fire so the
        # caller sees a populated run.json with judge_error notes.
        for pair_key, img_a, img_b in _discover_pairs(project_dir):
            data["judges"]["prompt"].append({
                "pair": pair_key, "judge": "prompt_judge",
                "scores": {"prompt_image_alignment": 3.0},
                "reasoning": "no gemini key (neutral fallback)",
                "model_used": "none", "cost_usd": 0.0,
            })
        write_run_json(project_dir, data)
        return data

    prompts = _load_prompts(project_dir)
    pairs = _discover_pairs(project_dir)
    video_dir = project_dir / "kling_test" / "videos"

    for pair_key, img_a, img_b in pairs:
        prompt_text = prompts.get(pair_key, "")
        # prompt_judge
        if not skip_prompt and prompt_text:
            try:
                pj = score_prompt(
                    image_a=img_a, image_b=img_b,
                    prompt_text=prompt_text, key=gemini_key,
                )
                entry = pj.model_dump()
                entry["pair"] = pair_key
                data["judges"]["prompt"].append(entry)
            except Exception as exc:  # pragma: no cover (parser-side falls back internally)
                data["judges"]["prompt"].append({
                    "pair": pair_key, "judge": "prompt_judge",
                    "scores": {"prompt_image_alignment": 3.0},
                    "reasoning": f"orchestrator error: {exc!r}",
                    "model_used": "error", "cost_usd": 0.0,
                })

        # clip_judge
        clip_path = video_dir / f"seg_{pair_key}.mp4"
        if not skip_clip and clip_path.is_file():
            try:
                cj = score_clip(
                    video_path=clip_path,
                    prompt_text=prompt_text or "(no prompt)",
                    key=gemini_key,
                )
                entry = cj.model_dump()
                entry["pair"] = pair_key
                data["judges"]["clip"].append(entry)
            except Exception as exc:  # pragma: no cover
                data["judges"]["clip"].append({
                    "pair": pair_key, "judge": "clip_judge",
                    "scores": {
                        "visual_quality": 3.0,
                        "style_consistency": 3.0,
                        "prompt_match": 3.0,
                        "anatomy_ok": True,
                    },
                    "reasoning": f"orchestrator error: {exc!r}",
                    "model_used": "error", "cost_usd": 0.0,
                })

    data["cost_usd_total"] = _recompute_cost(data)
    write_run_json(project_dir, data)
    return data


# --- post-stitch judge -----------------------------------------------

def run_post_stitch_judge(
    project_dir: Path,
    deepseek_key: str | None = None,
    *,
    story_arc: dict[str, Any] | None = None,
    brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run movie_judge over per-clip judge results. Persists to run.json.

    Reads the existing `judges.clip` list as input. If empty, judges
    cannot run (movie_judge needs per-clip data); writes a placeholder
    entry noting the missing input.
    """
    project_dir = Path(project_dir)
    if deepseek_key is None:
        deepseek_key = os.getenv("DEEPSEEK_KEY") or ""

    data = read_run_json(project_dir)
    clip_judges = [c.get("scores", {}) | {"pair": c.get("pair"), "reasoning": c.get("reasoning", "")}
                   for c in data["judges"].get("clip", []) or []]

    if not clip_judges:
        data["judges"]["movie"] = {
            "judge": "movie_judge",
            "scores": {
                "story_coherence": 3.0,
                "character_continuity": 3.0,
                "visual_quality": 3.0,
                "emotional_arc": 3.0,
            },
            "reasoning": "no per-clip judge data available; movie_judge skipped",
            "model_used": "none", "cost_usd": 0.0,
        }
        write_run_json(project_dir, data)
        return data

    if not deepseek_key:
        data["judges"]["movie"] = {
            "judge": "movie_judge",
            "scores": {
                "story_coherence": 3.0,
                "character_continuity": 3.0,
                "visual_quality": 3.0,
                "emotional_arc": 3.0,
            },
            "reasoning": "no DEEPSEEK_KEY (neutral fallback)",
            "model_used": "none", "cost_usd": 0.0,
        }
        write_run_json(project_dir, data)
        return data

    try:
        mj = score_movie(
            clip_judges=clip_judges,
            story_arc=story_arc,
            brief=brief,
            key=deepseek_key,
        )
        data["judges"]["movie"] = mj.model_dump()
    except Exception as exc:  # pragma: no cover
        data["judges"]["movie"] = {
            "judge": "movie_judge",
            "scores": {
                "story_coherence": 3.0,
                "character_continuity": 3.0,
                "visual_quality": 3.0,
                "emotional_arc": 3.0,
            },
            "reasoning": f"orchestrator error: {exc!r}",
            "model_used": "error", "cost_usd": 0.0,
        }

    data["cost_usd_total"] = _recompute_cost(data)
    write_run_json(project_dir, data)
    return data
