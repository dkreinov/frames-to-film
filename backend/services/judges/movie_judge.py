"""movie_judge — post-stitch coherence reasoning.

Text-only. Reads per-clip judge JSON + story arc paragraph + brief, asks
a cheap reasoning model to score story coherence + character continuity
+ emotional arc, and pick the weakest seam.

Default model: deepseek-chat (DeepSeek V4 Flash via OpenAI-compatible
endpoint). Step 4.5 benchmark may swap.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from backend.services.judges.base import JudgeScore, estimate_cost

DEFAULT_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

_RUBRIC_PROMPT = (
    "You are a film-editor critic scoring a short AI-generated movie. "
    "You see per-clip judge results (each clip already scored on visual "
    "quality + anatomy + prompt-match), the intended story arc, and the "
    "operator's brief. You do NOT see the video itself.\n\n"
    "Rate the assembled sequence on these dimensions, each 1-5:\n"
    "  story_coherence: do the clips tell the intended story?\n"
    "  character_continuity: same character/subject preserved across clips?\n"
    "  visual_quality: derived from per-clip visual scores; weighted by "
    "how much each clip's issue affects the whole.\n"
    "  emotional_arc: does the sequence build/release tension as the "
    "arc-type expects?\n\n"
    "Identify the weakest seam (1-indexed pair number where the worst "
    "transition lives), or null if no seam is clearly worst.\n\n"
    "Respond with strict JSON only, no preamble:\n"
    '{"story_coherence": <float>, "character_continuity": <float>, '
    '"visual_quality": <float>, "emotional_arc": <float>, '
    '"weakest_seam": <int or null>, '
    '"reasoning": "<one paragraph: what works, what breaks, what to fix first>"}'
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


def _build_user_message(
    *,
    clip_judges: list[dict[str, Any]],
    story_arc: dict[str, Any] | None,
    brief: dict[str, Any] | None,
) -> str:
    parts: list[str] = []
    if brief:
        parts.append("OPERATOR BRIEF:")
        parts.append(json.dumps(brief, indent=2))
    if story_arc:
        parts.append("\nSTORY ARC:")
        parts.append(json.dumps(story_arc, indent=2))
    parts.append("\nPER-CLIP JUDGE RESULTS:")
    parts.append(json.dumps(clip_judges, indent=2))
    return "\n".join(parts)


def _call_deepseek(
    *,
    user_message: str,
    key: str,
    model: str,
) -> tuple[str, int, int]:
    """OpenAI-compatible chat completion against DeepSeek API."""
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _RUBRIC_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    in_tok = int(usage.get("prompt_tokens", 0) or 0)
    out_tok = int(usage.get("completion_tokens", 0) or 0)
    return text, in_tok, out_tok


def score_movie(
    *,
    clip_judges: list[dict[str, Any]],
    story_arc: dict[str, Any] | None = None,
    brief: dict[str, Any] | None = None,
    key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> JudgeScore:
    """Score a stitched movie via reasoning over per-clip judge JSON.

    `clip_judges`: list of dicts (typically one per pair, the `scores`
    field of each `JudgeScore`).
    `story_arc`: the story.json from 7.4 (None pre-7.4 — judge falls
    back to inferring from clip data alone).
    `brief`: operator's subject/tone/notes (None if not provided).

    `key`: DeepSeek key. Reads `DEEPSEEK_KEY` env if not passed.
    """
    if key is None:
        key = os.getenv("DEEPSEEK_KEY", "")
    if not key:
        return JudgeScore(
            judge="movie_judge",
            scores={
                "story_coherence": 3.0,
                "character_continuity": 3.0,
                "visual_quality": 3.0,
                "emotional_arc": 3.0,
            },
            reasoning="DEEPSEEK_KEY not set; neutral fallback.",
            model_used=model,
        )

    user_msg = _build_user_message(
        clip_judges=clip_judges, story_arc=story_arc, brief=brief
    )
    try:
        text, in_tok, out_tok = _call_deepseek(
            user_message=user_msg, key=key, model=model
        )
        data = _parse_response(text)
    except Exception as exc:
        return JudgeScore(
            judge="movie_judge",
            scores={
                "story_coherence": 3.0,
                "character_continuity": 3.0,
                "visual_quality": 3.0,
                "emotional_arc": 3.0,
            },
            reasoning=f"judge error (neutral fallback): {exc!r}",
            model_used=model,
        )

    weakest = data.get("weakest_seam")
    if weakest is not None:
        try:
            weakest = int(weakest)
        except (TypeError, ValueError):
            weakest = None

    scores = {
        "story_coherence": float(data.get("story_coherence", 3.0)),
        "character_continuity": float(data.get("character_continuity", 3.0)),
        "visual_quality": float(data.get("visual_quality", 3.0)),
        "emotional_arc": float(data.get("emotional_arc", 3.0)),
    }
    return JudgeScore(
        judge="movie_judge",
        scores=scores,
        reasoning=str(data.get("reasoning", "")).strip(),
        weakest_seam=weakest,
        model_used=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=estimate_cost(model, in_tok, out_tok),
    )
