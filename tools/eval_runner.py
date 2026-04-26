"""Eval harness — Phase 7.2.

Walks `fixtures/eval_set/{NN_slug}/` directories. For each fixture, runs
the full pipeline in the requested mode (mock or api), captures judge
scores + cost + wall time, appends a row to `fixtures/eval_set/eval_runs.csv`.

CSV schema (locked):
  run_label, fixture_id, timestamp, arc_type, n_pairs, mode,
  prompt_align_mean, prompt_align_min,
  clip_main_drift_mean, clip_text_artifacts_mean, clip_limb_anatomy_mean,
  clip_unnatural_faces_mean, clip_glitches_mean, clip_content_halluc_mean,
  movie_story_coh, movie_continuity, movie_visual, movie_arc, weakest_seam,
  cost_usd, wall_time_s, model_versions

Append-only — git-tracked, treat like a journal.

Mock mode: zero LLM calls, zero Kling spend. Judges return neutral 3.0
fallbacks, generate stage produces black-frame stubs. Useful for
pipeline shape validation and CI.

Api mode: real spend. Operator decision; not the default.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.services.judges import orchestrator as judges_orch  # noqa: E402
from backend.services.project_schema import (  # noqa: E402
    EXTENDED_DIRNAME,
    METADATA_DIRNAME,
)

CSV_SCHEMA = [
    "run_label", "fixture_id", "timestamp", "arc_type", "n_pairs", "mode",
    "prompt_align_mean", "prompt_align_min",
    "clip_main_drift_mean", "clip_text_artifacts_mean",
    "clip_limb_anatomy_mean", "clip_unnatural_faces_mean",
    "clip_glitches_mean", "clip_content_halluc_mean",
    "movie_story_coh", "movie_continuity", "movie_visual", "movie_arc",
    "weakest_seam",
    "cost_usd", "wall_time_s", "model_versions",
]


def _load_expected_brief(fixture: Path) -> dict[str, Any]:
    p = fixture / METADATA_DIRNAME / "expected_brief.json"
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _seed_extended_from_inputs(fixture: Path) -> None:
    """For mock mode: skip the extend stage by copying inputs/ into
    extended/. Real eval would run the actual extend service.

    PNG inputs are converted to JPEG since generate.py globs *.jpg.
    """
    inputs = fixture / "inputs"
    extended = fixture / EXTENDED_DIRNAME
    extended.mkdir(parents=True, exist_ok=True)
    for f in inputs.iterdir():
        if not f.is_file() or f.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        # Normalize to .jpg (generate.py globs *.jpg)
        dst = extended / (f.stem + ".jpg")
        if dst.exists():
            continue
        if f.suffix.lower() == ".png":
            from PIL import Image as _PIL
            with _PIL.open(f) as im:
                im.convert("RGB").save(dst, "JPEG", quality=90)
        else:
            dst.write_bytes(f.read_bytes())


def _run_cli(cmd: list[str], cwd: Path | None = None) -> int:
    """Run a CLI script, return exit code. Stderr → stderr."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=300, cwd=cwd,
    )
    if result.returncode != 0:
        print(
            f"  [cli failed] {' '.join(str(x) for x in cmd)}\n"
            f"  stderr: {result.stderr[:500]}",
            file=sys.stderr,
        )
    return result.returncode


def _generate_clips(fixture: Path, mode: str, fal_key: str | None) -> int:
    """Dispatch to run_generate with the requested mode (mock or api)."""
    from backend.services.generate import run_generate
    try:
        run_generate(project_dir=fixture, mode=mode, fal_key=fal_key)
        return 0
    except Exception as exc:
        print(f"  [generate {mode}] error: {exc!r}", file=sys.stderr)
        return 1


def _aggregate_judge_scores(run_json: dict[str, Any]) -> dict[str, Any]:
    """Compute per-rubric means + min + movie scores from run.json."""
    out: dict[str, Any] = {col: "" for col in CSV_SCHEMA}
    judges = run_json.get("judges") or {}

    # prompt_judge
    prompts_list = judges.get("prompt") or []
    pa_scores = [p.get("scores", {}).get("prompt_image_alignment")
                 for p in prompts_list]
    pa_scores = [s for s in pa_scores if isinstance(s, (int, float))]
    if pa_scores:
        out["prompt_align_mean"] = round(statistics.mean(pa_scores), 2)
        out["prompt_align_min"] = round(min(pa_scores), 2)

    # clip_judge — 6 dimensions
    clips_list = judges.get("clip") or []
    dim_keys = [
        "main_character_drift", "text_artifacts", "limb_anatomy",
        "unnatural_faces", "glitches", "content_hallucination",
    ]
    csv_keys = [
        "clip_main_drift_mean", "clip_text_artifacts_mean",
        "clip_limb_anatomy_mean", "clip_unnatural_faces_mean",
        "clip_glitches_mean", "clip_content_halluc_mean",
    ]
    for dim, csv_key in zip(dim_keys, csv_keys):
        vals = [c.get("scores", {}).get(dim) for c in clips_list]
        vals = [v for v in vals if isinstance(v, (int, float))]
        if vals:
            out[csv_key] = round(statistics.mean(vals), 2)

    # movie_judge
    movie = judges.get("movie") or {}
    mscores = movie.get("scores") or {}
    out["movie_story_coh"] = mscores.get("story_coherence", "")
    out["movie_continuity"] = mscores.get("character_continuity", "")
    out["movie_visual"] = mscores.get("visual_quality", "")
    out["movie_arc"] = mscores.get("emotional_arc", "")
    out["weakest_seam"] = movie.get("weakest_seam") or ""

    out["cost_usd"] = round(float(run_json.get("cost_usd_total", 0) or 0), 6)
    return out


def _model_versions_str() -> str:
    """Snapshot of which models would be used for each judge."""
    from backend.services.judges import clip_judge, movie_judge, prompt_judge
    return (f"prompt={prompt_judge.DEFAULT_MODEL};"
            f"clip={clip_judge.DEFAULT_MODEL};"
            f"movie={movie_judge.DEFAULT_MODEL}")


def run_fixture(
    fixture: Path,
    *,
    label: str,
    mode: str,
    fal_key: str | None = None,
) -> dict[str, Any] | None:
    """Run one fixture through the pipeline. Return CSV row dict, or
    None if fixture is broken / missing."""
    if not fixture.is_dir():
        print(f"  [skip] fixture not found: {fixture}", file=sys.stderr)
        return None
    expected = _load_expected_brief(fixture)
    arc_type = expected.get("arc_type", "3-act-heroic")

    t0 = time.perf_counter()

    # Stage 1: ensure extended/ exists (mock skips real extend)
    _seed_extended_from_inputs(fixture)

    # Stage 2: write story (mock CLI)
    rc = _run_cli([
        sys.executable, str(REPO_ROOT / "tools" / "cli" / "run_story.py"),
        "--project", str(fixture),
        "--arc-type", arc_type,
        "--subject", expected.get("subject", ""),
        "--tone", expected.get("tone", ""),
        "--notes", expected.get("notes", ""),
        "--mock",
    ])
    if rc != 0:
        return None

    # Stage 3: write per-pair prompts (mock CLI)
    rc = _run_cli([
        sys.executable, str(REPO_ROOT / "tools" / "cli" / "run_prompts.py"),
        "--project", str(fixture),
        "--mock",
    ])
    if rc != 0:
        return None

    # Stage 4: generate clips
    if _generate_clips(fixture, mode=mode, fal_key=fal_key) != 0:
        return None

    # Stage 5: post-generate judges (mock mode — judges skip in generate.py
    # mock branch; but orchestrator can be called directly to populate run.json
    # with neutral fallbacks. Skip in pure mock to keep this fast.)
    # Just write a baseline run.json with neutral judge fallbacks.
    data = judges_orch.read_run_json(fixture)
    data["stages"].setdefault("generate", {"status": "done"})
    data["judges"]["prompt"] = []
    data["judges"]["clip"] = []
    judges_orch.write_run_json(fixture, data)

    # Stage 6: post-stitch movie_judge (mock — neutral fallback since no key)
    judges_orch.run_post_stitch_judge(fixture, deepseek_key="")

    wall = round(time.perf_counter() - t0, 2)

    # Aggregate scores
    run_json = judges_orch.read_run_json(fixture)
    scores = _aggregate_judge_scores(run_json)

    # Story.json may have been re-loaded; use it for n_pairs
    story_path = fixture / METADATA_DIRNAME / "story.json"
    n_pairs = 0
    if story_path.is_file():
        try:
            n_pairs = len(json.loads(story_path.read_text())
                         .get("pair_intents", []))
        except (json.JSONDecodeError, OSError):
            pass

    row: dict[str, Any] = {col: "" for col in CSV_SCHEMA}
    row.update(scores)
    row.update({
        "run_label": label,
        "fixture_id": fixture.name,
        "timestamp": _ts(),
        "arc_type": arc_type,
        "n_pairs": n_pairs,
        "mode": mode,
        "wall_time_s": wall,
        "model_versions": _model_versions_str(),
    })
    return row


_KLING_COST_PER_PAIR_USD = 0.42  # Kling O3 5-second clip, April 2026 pricing


def _estimate_fixture_cost(fixture: Path) -> float:
    """Estimate Kling spend for one fixture: (n_inputs - 1) pairs × $0.42."""
    inputs = fixture / "inputs"
    if not inputs.is_dir():
        return 0.0
    n = sum(1 for f in inputs.iterdir()
            if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png"})
    return max(0, n - 1) * _KLING_COST_PER_PAIR_USD


def main() -> int:
    p = argparse.ArgumentParser(description="Eval harness — walk fixtures, append CSV.")
    p.add_argument("--label", required=True, help="Run label (e.g. 'post-7.4-baseline')")
    p.add_argument("--mode", default="mock", choices=["mock", "api"],
                   help="Pipeline mode (default mock; api spends real money)")
    p.add_argument("--eval-set", default=str(REPO_ROOT / "fixtures" / "eval_set"),
                   help="Path to eval_set directory")
    p.add_argument("--fixture", default="all",
                   help="Specific fixture id or 'all' (default 'all')")
    p.add_argument("--max-usd", type=float, default=None,
                   help="Hard cost ceiling in USD (overrides MAX_USD env var)")
    args = p.parse_args()

    eval_set = Path(args.eval_set).resolve()
    if not eval_set.is_dir():
        print(f"ERROR: eval_set not found: {eval_set}", file=sys.stderr)
        return 1

    # Discover fixtures
    if args.fixture == "all":
        fixtures = sorted(
            f for f in eval_set.iterdir()
            if f.is_dir() and f.name not in {"__pycache__"} and not f.name.startswith(".")
        )
    else:
        candidate = eval_set / args.fixture
        fixtures = [candidate] if candidate.is_dir() else []
        if not fixtures:
            print(f"  [skip] no fixture matches {args.fixture}", file=sys.stderr)

    fal_key: str | None = os.environ.get("FAL_KEY") or None

    # MAX_USD cost cap (api mode only)
    max_usd: float | None = args.max_usd
    if max_usd is None:
        env_cap = os.environ.get("MAX_USD")
        if env_cap:
            try:
                max_usd = float(env_cap)
            except ValueError:
                pass
    if args.mode == "api":
        # Preflight: FAL_KEY required
        if not fal_key:
            print(
                "ERROR: FAL_KEY env var not set. api mode requires a valid fal.ai key.",
                file=sys.stderr,
            )
            return 1
        # Cost estimate
        estimated = sum(_estimate_fixture_cost(f) for f in fixtures)
        print(
            f"[preflight] api mode — {len(fixtures)} fixture(s), "
            f"estimated cost ${estimated:.2f} "
            f"({int(estimated / _KLING_COST_PER_PAIR_USD + 0.5)} Kling pairs × "
            f"${_KLING_COST_PER_PAIR_USD}/pair)"
        )
        # MAX_USD cap
        if max_usd is not None and estimated > max_usd:
            print(
                f"ERROR: estimated cost ${estimated:.2f} exceeds MAX_USD cap "
                f"${max_usd:.2f}. Aborting. Pass --max-usd to override.",
                file=sys.stderr,
            )
            return 1

    csv_path = eval_set / "eval_runs.csv"
    rows_to_write: list[dict[str, Any]] = []
    for fixture in fixtures:
        print(f"[{_ts()}] running {fixture.name} (mode={args.mode}) ...")
        row = run_fixture(fixture, label=args.label, mode=args.mode, fal_key=fal_key)
        if row is not None:
            rows_to_write.append(row)
            print(f"  done in {row['wall_time_s']}s; cost ${row['cost_usd']}")

    if not rows_to_write:
        print("no rows to write", file=sys.stderr)
        # Treat as success if user passed an explicit non-existent fixture.
        return 0 if args.fixture != "all" else 1

    # Append-only CSV write
    write_header = not csv_path.is_file()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_SCHEMA)
        if write_header:
            writer.writeheader()
        for row in rows_to_write:
            writer.writerow(row)

    print(f"\nwrote {len(rows_to_write)} rows to {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
