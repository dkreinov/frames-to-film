"""clip_judge — post-render visual QA.

Samples 3 frames at 0.2s, 2.5s, 4.5s from a 5-second Kling clip; scores
the clip against the prompt that produced it. Drives the 1-reroll budget
when wired in 7.5.

Default model: gemini-2.5-flash (cheapest decent vision; already
plumbed). Step 4.5 benchmark may swap to 3-flash or 2.5-pro.
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from backend.services.judges.base import JudgeScore, estimate_cost
from backend.services.judges.ffmpeg_utils import extract_frames_at_timestamps

DEFAULT_MODEL = "gemini-3-flash-preview"
"""Pick from Step 4.5 benchmark — 3-flash-preview catches anatomy issues
that 2.5-flash misses (verified on wet-test pair 2→3 hand-merge artifact).
Free during preview; ~$0.001/call when priced. Fallback: 'gemini-2.5-flash'."""

DEFAULT_TIMESTAMPS_S = [0.2, 2.5, 4.5]

_RUBRIC_HEAD = (
    "You are reviewing 3 frames sampled from a 5-second AI-generated "
    "video clip (start, middle, end). Rate the clip on these dimensions, "
    "each 1-5 (or boolean for anatomy):\n"
    "  visual_quality: overall fidelity, sharpness, lighting, no glitches\n"
    "  style_consistency: do the 3 frames feel like the same shot?\n"
    "  prompt_match: does the visible content match the prompt?\n"
    "  anatomy_ok: true if hands/faces/bodies look natural; false if "
    "broken (extra fingers, melting faces, joints bending wrong, etc.)\n\n"
    "Respond with strict JSON only, no preamble:\n"
    '{"visual_quality": <float 1-5>, "style_consistency": <float 1-5>, '
    '"prompt_match": <float 1-5>, "anatomy_ok": <bool>, '
    '"reasoning": "<one sentence describing the worst issue, or empty>"}'
)


def _build_rubric(prompt_text: str) -> str:
    return (
        f"{_RUBRIC_HEAD}\n\nThe clip was generated from this prompt:\n"
        f"---\n{prompt_text}\n---"
    )


def _parse_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if not m:
            raise ValueError(f"could not parse JSON: {text[:200]}")
        return json.loads(m.group(0))


def _call_gemini_vision(
    *,
    frame_paths: list[Path],
    prompt_text: str,
    key: str,
    model: str,
) -> tuple[str, int, int]:
    from google import genai
    from PIL import Image

    client = genai.Client(**{"api_key": key})
    images = [Image.open(p) for p in frame_paths]
    rubric = _build_rubric(prompt_text)
    resp = client.models.generate_content(
        model=model, contents=[rubric, *images]
    )
    text = (resp.text or "").strip()
    usage = getattr(resp, "usage_metadata", None)
    in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
    out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
    return text, in_tok, out_tok


def score_clip(
    *,
    video_path: Path,
    prompt_text: str,
    key: str,
    model: str = DEFAULT_MODEL,
    timestamps_s: list[float] | None = None,
    frame_dir: Path | None = None,
) -> JudgeScore:
    """Score a 5s clip against its prompt. Returns JudgeScore.

    `frame_dir` defaults to a temp dir (cleaned automatically). Pass an
    explicit path to keep frames on disk for debugging.
    """
    timestamps = timestamps_s or DEFAULT_TIMESTAMPS_S
    cleanup_tmp = frame_dir is None
    if cleanup_tmp:
        tmp = tempfile.TemporaryDirectory()
        frame_dir = Path(tmp.name)
    else:
        tmp = None

    try:
        try:
            frames = extract_frames_at_timestamps(video_path, timestamps, frame_dir)
            text, in_tok, out_tok = _call_gemini_vision(
                frame_paths=frames,
                prompt_text=prompt_text,
                key=key,
                model=model,
            )
            data = _parse_response(text)
        except Exception as exc:
            return JudgeScore(
                judge="clip_judge",
                scores={
                    "visual_quality": 3.0,
                    "style_consistency": 3.0,
                    "prompt_match": 3.0,
                    "anatomy_ok": True,
                },
                reasoning=f"judge error (neutral fallback): {exc!r}",
                model_used=model,
            )

        scores: dict[str, Any] = {
            "visual_quality": float(data.get("visual_quality", 3.0)),
            "style_consistency": float(data.get("style_consistency", 3.0)),
            "prompt_match": float(data.get("prompt_match", 3.0)),
            "anatomy_ok": bool(data.get("anatomy_ok", True)),
        }
        return JudgeScore(
            judge="clip_judge",
            scores=scores,
            reasoning=str(data.get("reasoning", "")).strip(),
            model_used=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=estimate_cost(model, in_tok, out_tok),
        )
    finally:
        if tmp is not None:
            tmp.cleanup()
