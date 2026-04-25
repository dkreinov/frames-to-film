"""Phase 7.1 Step 4.5 — judge model benchmark.

Runs each of the three judges against multiple model tiers using the
wet-test cat-astronaut fixtures, captures per-call score + latency +
cost, writes JSON for analysis + a markdown summary.

Cost cap: ~$0.50 total (early-exit if exceeded).

Usage:
    python tools/judge_benchmark.py
    python tools/judge_benchmark.py --skip clip   # skip a judge
    python tools/judge_benchmark.py --quick       # 1 model per judge

Reads keys from .env via os.getenv:
    gemini, DEEPSEEK_KEY, FAL_KEY (FAL not needed; existing fixtures used)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean, pstdev

# Ensure backend/ on path when run from repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.services.judges import score_clip, score_movie, score_prompt  # noqa: E402

FIXTURE_PROJECT = REPO_ROOT / "pipeline_runs" / "local" / "3fadfa16c6454ac28f336f612ca58e2b"
KLING_DIR = FIXTURE_PROJECT / "kling_test"
VIDEO_DIR = KLING_DIR / "videos"
PROMPTS_PATH = FIXTURE_PROJECT / "prompts.json"

# Models to compare per judge.
PROMPT_JUDGE_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3-flash",
]
CLIP_JUDGE_MODELS = [
    "gemini-2.5-flash",
    "gemini-3-flash",
    "gemini-2.5-pro",
]
MOVIE_JUDGE_MODELS = [
    "deepseek-chat",          # V4 Flash
    "deepseek-reasoner",      # legacy R1, retiring 2026-07
]
# Note: gemini-3-pro for movie_judge would need a vision-free path;
# DeepSeek alone is enough to verify the cheap reasoner thesis.

# Synthetic per-clip judge data for movie_judge benchmark (no real run needed)
SYNTHETIC_CLIP_JUDGES = [
    {"pair": "1_to_2", "visual_quality": 4.2, "anatomy_ok": True,
     "style_consistency": 4.0, "prompt_match": 4.5,
     "reasoning": "Smooth transition, lighting holds."},
    {"pair": "2_to_3", "visual_quality": 2.8, "anatomy_ok": False,
     "style_consistency": 3.0, "prompt_match": 3.2,
     "reasoning": "Hand merging with package edge; anatomy break."},
    {"pair": "3_to_4", "visual_quality": 3.8, "anatomy_ok": True,
     "style_consistency": 3.5, "prompt_match": 3.8,
     "reasoning": "Cosmic dust transition reads OK."},
    {"pair": "4_to_5", "visual_quality": 4.0, "anatomy_ok": True,
     "style_consistency": 4.2, "prompt_match": 4.0,
     "reasoning": "Strong dolly-in feel."},
    {"pair": "5_to_6", "visual_quality": 4.1, "anatomy_ok": True,
     "style_consistency": 4.0, "prompt_match": 4.2,
     "reasoning": "Final frame holds; shimmer effect looks plausible."},
]

SYNTHETIC_STORY_ARC = {
    "arc_paragraph": (
        "A cat astronaut journeys across a glowing alien moonscape, "
        "discovers a package amid bioluminescent mushrooms, and returns "
        "transformed by the encounter."
    ),
    "pair_intents": [
        {"from": 1, "to": 2, "intent": "Approach the mushroom field"},
        {"from": 2, "to": 3, "intent": "Discover the package"},
        {"from": 3, "to": 4, "intent": "Grasp the package, reality shifts"},
        {"from": 4, "to": 5, "intent": "Cosmic transformation moment"},
        {"from": 5, "to": 6, "intent": "Return, changed"},
    ],
}

SYNTHETIC_BRIEF = {
    "subject": "Cat astronaut",
    "tone": "wonder, otherworldly",
    "notes": "Heroic 3-act mini-story, ~25 seconds total.",
}


def _ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _bench_prompt_judge(
    *, gemini_key: str, models: list[str], runs_per_model: int = 2
) -> list[dict]:
    """Run prompt_judge across models on 5 wet-test prompts × runs_per_model."""
    prompts = json.loads(PROMPTS_PATH.read_text())
    results: list[dict] = []
    for model in models:
        per_call: list[dict] = []
        for pair_key, prompt_text in prompts.items():
            a_stem, b_stem = pair_key.split("_to_")
            img_a = KLING_DIR / f"{a_stem}.jpg"
            img_b = KLING_DIR / f"{b_stem}.jpg"
            if not (img_a.exists() and img_b.exists()):
                print(f"  skip {pair_key}: missing source images", file=sys.stderr)
                continue
            for run_n in range(runs_per_model):
                t0 = time.perf_counter()
                js = score_prompt(
                    image_a=img_a, image_b=img_b, prompt_text=prompt_text,
                    key=gemini_key, model=model,
                )
                dt = time.perf_counter() - t0
                per_call.append({
                    "pair": pair_key, "run": run_n,
                    "score": js.scores.get("prompt_image_alignment"),
                    "cost": js.cost_usd, "latency_s": round(dt, 2),
                    "tokens_in": js.input_tokens, "tokens_out": js.output_tokens,
                    "reasoning_excerpt": js.reasoning[:120],
                })
        scores = [c["score"] for c in per_call if isinstance(c["score"], (int, float))]
        results.append({
            "judge": "prompt_judge", "model": model,
            "n_calls": len(per_call),
            "score_mean": round(mean(scores), 2) if scores else None,
            "score_stdev": round(pstdev(scores), 2) if len(scores) > 1 else 0.0,
            "cost_total_usd": round(sum(c["cost"] for c in per_call), 5),
            "cost_per_call_usd": round(sum(c["cost"] for c in per_call) / max(len(per_call), 1), 6),
            "latency_mean_s": round(mean(c["latency_s"] for c in per_call), 2) if per_call else None,
            "calls": per_call,
        })
    return results


def _bench_clip_judge(
    *, gemini_key: str, models: list[str], runs_per_model: int = 1
) -> list[dict]:
    """Run clip_judge on each of 5 segment mp4s × runs_per_model."""
    prompts = json.loads(PROMPTS_PATH.read_text())
    results: list[dict] = []
    for model in models:
        per_call: list[dict] = []
        for pair_key, prompt_text in prompts.items():
            video_path = VIDEO_DIR / f"seg_{pair_key}.mp4"
            if not video_path.exists():
                print(f"  skip {pair_key}: missing {video_path}", file=sys.stderr)
                continue
            for run_n in range(runs_per_model):
                t0 = time.perf_counter()
                js = score_clip(
                    video_path=video_path, prompt_text=prompt_text,
                    key=gemini_key, model=model,
                )
                dt = time.perf_counter() - t0
                per_call.append({
                    "pair": pair_key, "run": run_n,
                    "visual_quality": js.scores.get("visual_quality"),
                    "anatomy_ok": js.scores.get("anatomy_ok"),
                    "prompt_match": js.scores.get("prompt_match"),
                    "cost": js.cost_usd, "latency_s": round(dt, 2),
                    "tokens_in": js.input_tokens, "tokens_out": js.output_tokens,
                    "reasoning_excerpt": js.reasoning[:120],
                })
        vqs = [c["visual_quality"] for c in per_call if isinstance(c["visual_quality"], (int, float))]
        anatomy_breaks = sum(1 for c in per_call if c.get("anatomy_ok") is False)
        results.append({
            "judge": "clip_judge", "model": model,
            "n_calls": len(per_call),
            "visual_quality_mean": round(mean(vqs), 2) if vqs else None,
            "visual_quality_stdev": round(pstdev(vqs), 2) if len(vqs) > 1 else 0.0,
            "anatomy_breaks_flagged": anatomy_breaks,
            "cost_total_usd": round(sum(c["cost"] for c in per_call), 5),
            "cost_per_call_usd": round(sum(c["cost"] for c in per_call) / max(len(per_call), 1), 6),
            "latency_mean_s": round(mean(c["latency_s"] for c in per_call), 2) if per_call else None,
            "calls": per_call,
        })
    return results


def _bench_movie_judge(
    *, deepseek_key: str, models: list[str], runs_per_model: int = 2
) -> list[dict]:
    """Run movie_judge with synthetic data × runs_per_model."""
    results: list[dict] = []
    for model in models:
        per_call: list[dict] = []
        for run_n in range(runs_per_model):
            t0 = time.perf_counter()
            js = score_movie(
                clip_judges=SYNTHETIC_CLIP_JUDGES,
                story_arc=SYNTHETIC_STORY_ARC,
                brief=SYNTHETIC_BRIEF,
                key=deepseek_key, model=model,
            )
            dt = time.perf_counter() - t0
            per_call.append({
                "run": run_n,
                "story_coherence": js.scores.get("story_coherence"),
                "character_continuity": js.scores.get("character_continuity"),
                "emotional_arc": js.scores.get("emotional_arc"),
                "weakest_seam": js.weakest_seam,
                "cost": js.cost_usd, "latency_s": round(dt, 2),
                "tokens_in": js.input_tokens, "tokens_out": js.output_tokens,
                "reasoning_excerpt": js.reasoning[:240],
            })
        sc = [c["story_coherence"] for c in per_call if isinstance(c["story_coherence"], (int, float))]
        results.append({
            "judge": "movie_judge", "model": model,
            "n_calls": len(per_call),
            "story_coherence_mean": round(mean(sc), 2) if sc else None,
            "story_coherence_stdev": round(pstdev(sc), 2) if len(sc) > 1 else 0.0,
            "weakest_seam_picks": [c["weakest_seam"] for c in per_call],
            "cost_total_usd": round(sum(c["cost"] for c in per_call), 5),
            "cost_per_call_usd": round(sum(c["cost"] for c in per_call) / max(len(per_call), 1), 6),
            "latency_mean_s": round(mean(c["latency_s"] for c in per_call), 2) if per_call else None,
            "calls": per_call,
        })
    return results


def _format_markdown(results_by_judge: dict[str, list[dict]]) -> str:
    lines: list[str] = []
    lines.append("# Judge Model Benchmark — Phase 7.1 Step 4.5")
    lines.append("")
    lines.append(f"**Date:** {_ts()}")
    lines.append(f"**Fixture:** wet-test cat-astronaut project (5 prompts, 5 mp4s)")
    lines.append("")

    for judge_name, results in results_by_judge.items():
        lines.append(f"## {judge_name}")
        lines.append("")
        if not results:
            lines.append("_(skipped)_")
            lines.append("")
            continue
        if judge_name == "prompt_judge":
            lines.append("| Model | n | mean score | stdev | $/call | latency (s) |")
            lines.append("|---|---|---|---|---|---|")
            for r in results:
                lines.append(
                    f"| `{r['model']}` | {r['n_calls']} | {r['score_mean']} | "
                    f"{r['score_stdev']} | ${r['cost_per_call_usd']} | "
                    f"{r['latency_mean_s']} |"
                )
        elif judge_name == "clip_judge":
            lines.append("| Model | n | mean visual | stdev | anatomy breaks | $/call | latency (s) |")
            lines.append("|---|---|---|---|---|---|---|")
            for r in results:
                lines.append(
                    f"| `{r['model']}` | {r['n_calls']} | {r['visual_quality_mean']} | "
                    f"{r['visual_quality_stdev']} | {r['anatomy_breaks_flagged']} | "
                    f"${r['cost_per_call_usd']} | {r['latency_mean_s']} |"
                )
        elif judge_name == "movie_judge":
            lines.append("| Model | n | mean story_coh | stdev | weakest seam picks | $/call | latency (s) |")
            lines.append("|---|---|---|---|---|---|---|")
            for r in results:
                lines.append(
                    f"| `{r['model']}` | {r['n_calls']} | {r['story_coherence_mean']} | "
                    f"{r['story_coherence_stdev']} | {r['weakest_seam_picks']} | "
                    f"${r['cost_per_call_usd']} | {r['latency_mean_s']} |"
                )
        lines.append("")

    lines.append("## Picks (filled in after analysis)")
    lines.append("")
    lines.append("- prompt_judge: TBD")
    lines.append("- clip_judge: TBD")
    lines.append("- movie_judge: TBD")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip", action="append", default=[],
                        choices=["prompt", "clip", "movie"],
                        help="Skip one or more judges")
    parser.add_argument("--quick", action="store_true",
                        help="Run only the cheapest model per judge")
    parser.add_argument("--out-json", default="docs/roadmap/judge_model_benchmark_2026-04.json")
    parser.add_argument("--out-md", default="docs/roadmap/judge_model_benchmark_2026-04.md")
    args = parser.parse_args()

    # Hard cost cap — abort if the benchmark exceeds this. Set via
    # MAX_USD env var; default $20 per user policy (2026-04-25). The
    # SDK self-report under-counts "thinking" tokens, so the *real*
    # spend can be higher than what we accumulate here. Treat this
    # as a soft estimate; verify against billing dashboard after run.
    max_usd = float(os.getenv("MAX_USD") or "20.0")
    print(f"[{_ts()}] cost cap: ${max_usd:.2f}")

    gemini_key = os.getenv("gemini") or ""
    deepseek_key = os.getenv("DEEPSEEK_KEY") or ""
    if not gemini_key:
        print("ERROR: gemini key missing in env (looked for 'gemini')", file=sys.stderr)
        return 1
    if not deepseek_key:
        print("WARN: DEEPSEEK_KEY missing — movie_judge benchmark will fall back to neutral", file=sys.stderr)

    prompt_models = PROMPT_JUDGE_MODELS[:1] if args.quick else PROMPT_JUDGE_MODELS
    clip_models = CLIP_JUDGE_MODELS[:1] if args.quick else CLIP_JUDGE_MODELS
    movie_models = MOVIE_JUDGE_MODELS[:1] if args.quick else MOVIE_JUDGE_MODELS

    results_by_judge: dict[str, list[dict]] = {}

    def _running_total() -> float:
        return sum(
            r.get("cost_total_usd", 0)
            for results in results_by_judge.values()
            for r in results
        )

    def _cap_check() -> bool:
        total = _running_total()
        if total >= max_usd:
            print(f"[{_ts()}] !! cost cap hit: ${total:.4f} >= ${max_usd:.2f} — aborting remaining stages")
            return True
        return False

    if "prompt" not in args.skip and not _cap_check():
        print(f"[{_ts()}] benchmarking prompt_judge: {prompt_models}")
        results_by_judge["prompt_judge"] = _bench_prompt_judge(
            gemini_key=gemini_key, models=prompt_models)
    else:
        results_by_judge["prompt_judge"] = []

    if "clip" not in args.skip and not _cap_check():
        print(f"[{_ts()}] benchmarking clip_judge: {clip_models}")
        results_by_judge["clip_judge"] = _bench_clip_judge(
            gemini_key=gemini_key, models=clip_models)
    else:
        results_by_judge["clip_judge"] = []

    if "movie" not in args.skip and not _cap_check():
        print(f"[{_ts()}] benchmarking movie_judge: {movie_models}")
        results_by_judge["movie_judge"] = _bench_movie_judge(
            deepseek_key=deepseek_key, models=movie_models)
    else:
        results_by_judge["movie_judge"] = []

    # Total cost guard
    total = sum(
        r.get("cost_total_usd", 0)
        for results in results_by_judge.values()
        for r in results
    )
    print(f"\n[{_ts()}] total benchmark cost: ${total:.4f}")

    out_json_path = REPO_ROOT / args.out_json
    out_md_path = REPO_ROOT / args.out_md
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(results_by_judge, indent=2))
    out_md_path.write_text(_format_markdown(results_by_judge))
    print(f"  json: {out_json_path}")
    print(f"  md:   {out_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
