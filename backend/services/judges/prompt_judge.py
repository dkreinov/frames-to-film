"""prompt_judge — pre-render gate.

Scores the alignment between a Kling prompt and the (image_a, image_b)
pair it'll be rendered against. Catches hallucinated prompts before the
$0.084 Kling spend.

Default model: gemini-2.5-flash-lite (cheapest vision tier per
`reference_model_prices_2026_04` memory). Step 4.5 benchmark may swap.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.services.judges.base import JudgeScore, estimate_cost

DEFAULT_MODEL = "gemini-2.5-flash-lite"

_RUBRIC_HEAD = (
    "You are scoring a Kling AI video-generation prompt against the two "
    "source frames it will animate between (image A is the start frame, "
    "image B is the end frame).\n\n"
    "Rate prompt-image alignment on a 1-5 scale where:\n"
    "  5 = prompt accurately describes a plausible motion between A and B; "
    "every concrete reference is grounded in what's visible.\n"
    "  4 = mostly grounded; minor stretch.\n"
    "  3 = generic but not contradicted by the images.\n"
    "  2 = describes things that aren't in either image, or contradicts them.\n"
    "  1 = totally hallucinated; references missing subjects/objects/places.\n\n"
    "Respond with strict JSON only, no preamble:\n"
    '{"score": <float 1-5>, "reasoning": "<one sentence>"}'
)


def _build_rubric(prompt_text: str) -> str:
    return f"{_RUBRIC_HEAD}\n\nPrompt to score:\n---\n{prompt_text}\n---"


def _parse_response(text: str) -> tuple[float, str]:
    """Pull score + reasoning from the model's JSON. Robust to ```json fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Last-resort: try to find a {...} block
        m = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
        if not m:
            raise ValueError(f"could not parse JSON from response: {text[:200]}")
        data = json.loads(m.group(0))
    score = float(data["score"])
    reasoning = str(data.get("reasoning", "")).strip()
    return score, reasoning


def _call_gemini_vision(
    *,
    image_a: Path,
    image_b: Path,
    prompt_text: str,
    key: str,
    model: str,
) -> tuple[str, int, int]:
    """Returns (response_text, input_tokens, output_tokens). Lazy import
    so unit tests can monkeypatch this whole function without touching
    google-genai SDK."""
    from google import genai
    from PIL import Image

    client = genai.Client(**{"api_key": key})
    img_a = Image.open(image_a)
    img_b = Image.open(image_b)
    rubric = _build_rubric(prompt_text)
    resp = client.models.generate_content(
        model=model, contents=[rubric, img_a, img_b]
    )
    text = (resp.text or "").strip()
    # google-genai returns usage_metadata with token counts
    usage = getattr(resp, "usage_metadata", None)
    in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
    out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
    return text, in_tok, out_tok


def score_prompt(
    *,
    image_a: Path,
    image_b: Path,
    prompt_text: str,
    key: str,
    model: str = DEFAULT_MODEL,
) -> JudgeScore:
    """Score one (image_a, image_b, prompt) tuple. Returns JudgeScore.

    Failure mode: if the LLM call or parsing fails, returns a neutral
    score (3.0) with an error message in `reasoning`. The caller
    (pipeline wiring 7.5) decides whether to gate on it.
    """
    try:
        text, in_tok, out_tok = _call_gemini_vision(
            image_a=image_a,
            image_b=image_b,
            prompt_text=prompt_text,
            key=key,
            model=model,
        )
        score, reasoning = _parse_response(text)
    except Exception as exc:  # log + neutral fallback, don't crash the run
        return JudgeScore(
            judge="prompt_judge",
            scores={"prompt_image_alignment": 3.0},
            reasoning=f"judge error (neutral fallback): {exc!r}",
            model_used=model,
        )

    return JudgeScore(
        judge="prompt_judge",
        scores={"prompt_image_alignment": score},
        reasoning=reasoning,
        model_used=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=estimate_cost(model, in_tok, out_tok),
    )
