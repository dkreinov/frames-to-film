"""Phase 7.1 strong-panel benchmark — Qwen + Kimi + Opus subagent.

Cross-vendor reference panel for the production cheap-judge stack.
NO Gemini calls (per user directive 2026-04-25 after billing audit).

Models per judge:
  prompt_judge: Qwen-VL-Plus + Moonshot vision-preview + Opus subagent
  clip_judge:   Qwen-VL-Plus + Moonshot vision-preview + Opus subagent
  movie_judge:  DeepSeek V4 Flash + Kimi K2.6 + Opus subagent

Opus subagent is invoked via the Claude Code Agent tool — runs at zero
marginal cost on the user's Claude session. Other models hit OpenAI-
compatible endpoints with bearer-token auth.

Cost cap: MAX_USD env var (default 20.00 USD).

Usage:
    python tools/strong_panel_benchmark.py
    python tools/strong_panel_benchmark.py --quick    # 1 fixture pair
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.services.judges.base import JudgeScore, estimate_cost  # noqa: E402
from backend.services.judges.ffmpeg_utils import extract_frames_at_timestamps  # noqa: E402

FIXTURE_PROJECT = REPO_ROOT / "pipeline_runs" / "local" / "3fadfa16c6454ac28f336f612ca58e2b"
KLING_DIR = FIXTURE_PROJECT / "kling_test"
VIDEO_DIR = KLING_DIR / "videos"
PROMPTS_PATH = FIXTURE_PROJECT / "prompts.json"


# --- vendor configuration --------------------------------------------

QWEN_BASE = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
MOONSHOT_BASE = "https://api.moonshot.ai/v1"
DEEPSEEK_BASE = "https://api.deepseek.com/v1"

# Models picked from earlier hello-world smokes
QWEN_VISION_MODEL = "qwen-vl-plus"
MOONSHOT_VISION_MODEL = "moonshot-v1-128k-vision-preview"
KIMI_TEXT_MODEL = "kimi-k2.6"
DEEPSEEK_TEXT_MODEL = "deepseek-chat"


# --- prompts (mirrored from production judges) -----------------------

PROMPT_JUDGE_RUBRIC = (
    "You are scoring a Kling AI video-generation prompt against the two "
    "source frames it will animate between (image A is the start frame, "
    "image B is the end frame).\n\n"
    "Rate prompt-image alignment 1-5. 5 = grounded; 3 = generic; 1 = hallucinated.\n\n"
    "Respond with strict JSON only, no preamble:\n"
    '{"score": <float 1-5>, "reasoning": "<one sentence>"}'
)

CLIP_JUDGE_RUBRIC = (
    "You are reviewing 3 frames sampled from a 5-second AI-generated "
    "video clip (start, middle, end). Rate the clip on:\n"
    "  visual_quality 1-5, style_consistency 1-5, prompt_match 1-5,\n"
    "  anatomy_ok (true=natural, false=broken).\n\n"
    "Respond with strict JSON only, no preamble:\n"
    '{"visual_quality": <float>, "style_consistency": <float>, '
    '"prompt_match": <float>, "anatomy_ok": <bool>, '
    '"reasoning": "<one sentence describing worst issue, or empty>"}'
)

MOVIE_JUDGE_RUBRIC = (
    "You are a film-editor critic scoring a short AI-generated movie. "
    "You see per-clip judge results, the intended story arc, and the brief.\n\n"
    "Rate 1-5: story_coherence, character_continuity, visual_quality, emotional_arc.\n"
    "Identify weakest seam (1-indexed pair number, or null).\n\n"
    "Respond with strict JSON only, no preamble:\n"
    '{"story_coherence": <float>, "character_continuity": <float>, '
    '"visual_quality": <float>, "emotional_arc": <float>, '
    '"weakest_seam": <int or null>, "reasoning": "<one paragraph>"}'
)


# --- response parsing ------------------------------------------------

def _parse_json(text: str) -> dict[str, Any]:
    import re
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if not m:
            raise ValueError(f"could not parse JSON from: {text[:200]}")
        return json.loads(m.group(0))


# --- OpenAI-compatible call helper -----------------------------------

def _openai_compat_call(
    *, base_url: str, key: str, model: str, messages: list,
    temperature: float = 0.0, response_json: bool = False,
) -> tuple[str, int, int]:
    payload = {"model": model, "messages": messages, "temperature": temperature}
    if response_json:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers=headers, json=payload, timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    in_tok = int(usage.get("prompt_tokens", 0) or 0)
    out_tok = int(usage.get("completion_tokens", 0) or 0)
    return text, in_tok, out_tok


def _img_to_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode()
    ext = path.suffix.lower().lstrip(".") or "jpeg"
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{b64}"


# --- per-vendor judge wrappers ---------------------------------------

def _vision_call(
    base_url: str, key: str, model: str,
    rubric: str, image_paths: list[Path],
) -> tuple[str, int, int]:
    content: list[Any] = [{"type": "text", "text": rubric}]
    for p in image_paths:
        content.append({"type": "image_url", "image_url": {"url": _img_to_data_uri(p)}})
    return _openai_compat_call(
        base_url=base_url, key=key, model=model,
        messages=[{"role": "user", "content": content}],
    )


def _opus_subagent_call(
    *, rubric: str, image_paths: list[Path],
    description: str = "Opus judge call",
) -> tuple[str, int, int]:
    """Stub. Real implementation requires the Agent tool from this script's
    parent process (not callable from a standalone Python script).

    For this benchmark, Opus subagent calls are made by the orchestrator
    that launches this script — see `tools/strong_panel_runner.md` for
    the runbook. This function exists so the JSON output schema is
    consistent across vendors; the runner fills in Opus results before
    final aggregation.
    """
    raise NotImplementedError("Opus subagent calls happen out-of-band; see runner")


# --- benchmark loops -------------------------------------------------

def _bench_prompt_judge(qwen_key: str, moonshot_key: str) -> dict[str, list[dict]]:
    prompts = json.loads(PROMPTS_PATH.read_text())
    out: dict[str, list[dict]] = {}

    for vendor, base, model, key in [
        ("qwen", QWEN_BASE, QWEN_VISION_MODEL, qwen_key),
        ("moonshot", MOONSHOT_BASE, MOONSHOT_VISION_MODEL, moonshot_key),
    ]:
        if not key:
            print(f"  skip {vendor}: no key")
            continue
        per_call: list[dict] = []
        for pair_key, prompt_text in prompts.items():
            a_stem, b_stem = pair_key.split("_to_")
            img_a = KLING_DIR / f"{a_stem}.jpg"
            img_b = KLING_DIR / f"{b_stem}.jpg"
            if not (img_a.exists() and img_b.exists()):
                continue
            full_rubric = (
                f"{PROMPT_JUDGE_RUBRIC}\n\nPrompt to score:\n---\n{prompt_text}\n---"
            )
            t0 = time.perf_counter()
            try:
                text, in_tok, out_tok = _vision_call(
                    base, key, model, full_rubric, [img_a, img_b]
                )
                data = _parse_json(text)
                score = float(data.get("score", 3.0))
                reasoning = str(data.get("reasoning", "")).strip()
                err = None
            except Exception as e:
                score, reasoning, in_tok, out_tok = 3.0, "", 0, 0
                err = repr(e)[:200]
            dt = time.perf_counter() - t0
            cost = estimate_cost(model, in_tok, out_tok)
            per_call.append({
                "pair": pair_key, "score": score,
                "tokens_in": in_tok, "tokens_out": out_tok,
                "cost": round(cost, 6), "latency_s": round(dt, 2),
                "reasoning": reasoning[:200], "error": err,
            })
        out[vendor] = per_call
    return out


def _bench_clip_judge(qwen_key: str, moonshot_key: str) -> dict[str, list[dict]]:
    prompts = json.loads(PROMPTS_PATH.read_text())
    out: dict[str, list[dict]] = {}
    timestamps = [0.2, 2.5, 4.5]

    for vendor, base, model, key in [
        ("qwen", QWEN_BASE, QWEN_VISION_MODEL, qwen_key),
        ("moonshot", MOONSHOT_BASE, MOONSHOT_VISION_MODEL, moonshot_key),
    ]:
        if not key:
            continue
        per_call: list[dict] = []
        import tempfile
        with tempfile.TemporaryDirectory() as tdir:
            tpath = Path(tdir)
            for pair_key, prompt_text in prompts.items():
                video = VIDEO_DIR / f"seg_{pair_key}.mp4"
                if not video.exists():
                    continue
                try:
                    frames = extract_frames_at_timestamps(video, timestamps, tpath / pair_key)
                except Exception as e:
                    per_call.append({
                        "pair": pair_key, "error": f"frame_extract: {e!r}",
                        "visual_quality": 3.0, "anatomy_ok": True,
                        "cost": 0, "latency_s": 0,
                    })
                    continue
                full_rubric = f"{CLIP_JUDGE_RUBRIC}\n\nPrompt:\n---\n{prompt_text}\n---"
                t0 = time.perf_counter()
                try:
                    text, in_tok, out_tok = _vision_call(base, key, model, full_rubric, frames)
                    data = _parse_json(text)
                    err = None
                except Exception as e:
                    data, in_tok, out_tok = {}, 0, 0
                    err = repr(e)[:200]
                dt = time.perf_counter() - t0
                cost = estimate_cost(model, in_tok, out_tok)
                per_call.append({
                    "pair": pair_key,
                    "visual_quality": float(data.get("visual_quality", 3.0)),
                    "style_consistency": float(data.get("style_consistency", 3.0)),
                    "prompt_match": float(data.get("prompt_match", 3.0)),
                    "anatomy_ok": bool(data.get("anatomy_ok", True)),
                    "tokens_in": in_tok, "tokens_out": out_tok,
                    "cost": round(cost, 6), "latency_s": round(dt, 2),
                    "reasoning": str(data.get("reasoning", ""))[:200], "error": err,
                })
        out[vendor] = per_call
    return out


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
     "reasoning": "Final frame holds; shimmer effect plausible."},
]
SYNTHETIC_STORY_ARC = {
    "arc_paragraph": "A cat astronaut journeys across a glowing alien moonscape, "
                     "discovers a package amid bioluminescent mushrooms, and "
                     "returns transformed.",
    "pair_intents": [
        {"from": 1, "to": 2, "intent": "Approach the mushroom field"},
        {"from": 2, "to": 3, "intent": "Discover the package"},
        {"from": 3, "to": 4, "intent": "Grasp it, reality shifts"},
        {"from": 4, "to": 5, "intent": "Cosmic transformation"},
        {"from": 5, "to": 6, "intent": "Return, changed"},
    ],
}
SYNTHETIC_BRIEF = {"subject": "Cat astronaut", "tone": "wonder, otherworldly",
                   "notes": "Heroic 3-act mini-story, ~25 seconds total."}


def _bench_movie_judge(deepseek_key: str, moonshot_key: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    user_msg = (
        "OPERATOR BRIEF:\n" + json.dumps(SYNTHETIC_BRIEF, indent=2) +
        "\n\nSTORY ARC:\n" + json.dumps(SYNTHETIC_STORY_ARC, indent=2) +
        "\n\nPER-CLIP JUDGE RESULTS:\n" + json.dumps(SYNTHETIC_CLIP_JUDGES, indent=2)
    )
    # K2.6 ignores `response_format: json_object` and only accepts
    # temperature=1; per-vendor overrides handle that.
    for vendor, base, model, key, temp, json_mode in [
        ("deepseek", DEEPSEEK_BASE, DEEPSEEK_TEXT_MODEL, deepseek_key, 0.0, True),
        ("kimi", MOONSHOT_BASE, KIMI_TEXT_MODEL, moonshot_key, 1.0, False),
    ]:
        if not key:
            continue
        per_call: list[dict] = []
        for run_n in range(2):
            t0 = time.perf_counter()
            try:
                text, in_tok, out_tok = _openai_compat_call(
                    base_url=base, key=key, model=model,
                    messages=[
                        {"role": "system", "content": MOVIE_JUDGE_RUBRIC},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=temp,
                    response_json=json_mode,
                )
                data = _parse_json(text)
                err = None
            except Exception as e:
                data, in_tok, out_tok = {}, 0, 0
                err = repr(e)[:200]
            dt = time.perf_counter() - t0
            cost = estimate_cost(model, in_tok, out_tok)
            weakest = data.get("weakest_seam")
            try:
                weakest = int(weakest) if weakest is not None else None
            except (TypeError, ValueError):
                weakest = None
            per_call.append({
                "run": run_n,
                "story_coherence": float(data.get("story_coherence", 3.0)),
                "character_continuity": float(data.get("character_continuity", 3.0)),
                "visual_quality": float(data.get("visual_quality", 3.0)),
                "emotional_arc": float(data.get("emotional_arc", 3.0)),
                "weakest_seam": weakest,
                "tokens_in": in_tok, "tokens_out": out_tok,
                "cost": round(cost, 6), "latency_s": round(dt, 2),
                "reasoning": str(data.get("reasoning", ""))[:300], "error": err,
            })
        out[vendor] = per_call
    return out


def _ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _running_total(results: dict) -> float:
    total = 0.0
    for stage in results.values():
        for vendor_calls in stage.values():
            for c in vendor_calls:
                total += float(c.get("cost", 0))
    return total


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out-json", default="docs/roadmap/strong_panel_results_2026-04.json")
    p.add_argument("--out-md", default="docs/roadmap/strong_panel_results_2026-04.md")
    args = p.parse_args()

    qwen = os.getenv("QWEEN_KEY") or ""    # user's chosen env name
    moonshot = os.getenv("KIMI_KEY") or ""
    deepseek = os.getenv("DEEPSEEK_KEY") or ""
    max_usd = float(os.getenv("MAX_USD") or "20.0")

    print(f"[{_ts()}] strong-panel benchmark (cap ${max_usd:.2f})")
    print(f"  qwen:     {'OK' if qwen else 'MISSING'}")
    print(f"  moonshot: {'OK' if moonshot else 'MISSING'}")
    print(f"  deepseek: {'OK' if deepseek else 'MISSING'}")

    results: dict[str, dict[str, list[dict]]] = {
        "prompt_judge": {}, "clip_judge": {}, "movie_judge": {}
    }

    print(f"\n[{_ts()}] running prompt_judge panel ...")
    results["prompt_judge"] = _bench_prompt_judge(qwen, moonshot)
    cost = _running_total(results)
    print(f"  running total: ${cost:.4f}")
    if cost >= max_usd:
        print(f"  CAP HIT — abort"); return 1

    print(f"\n[{_ts()}] running clip_judge panel ...")
    results["clip_judge"] = _bench_clip_judge(qwen, moonshot)
    cost = _running_total(results)
    print(f"  running total: ${cost:.4f}")
    if cost >= max_usd:
        print(f"  CAP HIT — abort"); return 1

    print(f"\n[{_ts()}] running movie_judge panel ...")
    results["movie_judge"] = _bench_movie_judge(deepseek, moonshot)

    total = _running_total(results)
    print(f"\n[{_ts()}] complete. total cost: ${total:.4f}")

    out_json = REPO_ROOT / args.out_json
    out_md = REPO_ROOT / args.out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, indent=2))
    out_md.write_text(_format_md(results, total))
    print(f"  json: {out_json}")
    print(f"  md:   {out_md}")
    return 0


def _format_md(results: dict, total: float) -> str:
    lines = [
        "# Strong-Panel Benchmark — Phase 7.1 follow-up",
        "",
        f"**Date:** {_ts()}",
        f"**Total cost:** ${total:.4f}",
        "**Models:** Qwen-VL-Plus, Moonshot-v1-128k-vision-preview, "
        "DeepSeek V4 Flash, Kimi K2.6",
        "**Note:** Opus 4.7 results to be added by the orchestrator subagent runner.",
        "",
        "## prompt_judge",
        "",
        "| Vendor | n | mean score | stdev | $/call | latency (s) |",
        "|---|---|---|---|---|---|",
    ]
    for vendor, calls in results["prompt_judge"].items():
        if not calls:
            continue
        scores = [c["score"] for c in calls if "error" not in (c.get("error") or "")]
        if not scores:
            scores = [c["score"] for c in calls]
        lines.append(
            f"| {vendor} | {len(calls)} | {mean(scores):.2f} | "
            f"{pstdev(scores) if len(scores)>1 else 0:.2f} | "
            f"${sum(c['cost'] for c in calls)/max(len(calls),1):.6f} | "
            f"{mean(c['latency_s'] for c in calls):.2f} |"
        )

    lines += ["", "## clip_judge", "",
              "| Vendor | n | mean visual | stdev | anatomy breaks | $/call | latency (s) |",
              "|---|---|---|---|---|---|---|"]
    for vendor, calls in results["clip_judge"].items():
        if not calls:
            continue
        vqs = [c["visual_quality"] for c in calls]
        breaks = sum(1 for c in calls if c.get("anatomy_ok") is False)
        lines.append(
            f"| {vendor} | {len(calls)} | {mean(vqs):.2f} | "
            f"{pstdev(vqs) if len(vqs)>1 else 0:.2f} | {breaks} | "
            f"${sum(c['cost'] for c in calls)/max(len(calls),1):.6f} | "
            f"{mean(c['latency_s'] for c in calls):.2f} |"
        )

    lines += ["", "## movie_judge", "",
              "| Vendor | n | mean story_coh | stdev | weakest seams | $/call | latency (s) |",
              "|---|---|---|---|---|---|---|"]
    for vendor, calls in results["movie_judge"].items():
        if not calls:
            continue
        sc = [c["story_coherence"] for c in calls]
        seams = [c["weakest_seam"] for c in calls]
        lines.append(
            f"| {vendor} | {len(calls)} | {mean(sc):.2f} | "
            f"{pstdev(sc) if len(sc)>1 else 0:.2f} | {seams} | "
            f"${sum(c['cost'] for c in calls)/max(len(calls),1):.6f} | "
            f"{mean(c['latency_s'] for c in calls):.2f} |"
        )

    lines += ["", "## Per-clip anatomy verdicts", "",
              "Comparison vs production cheap-judge (gemini-3-flash-preview).",
              ""]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
