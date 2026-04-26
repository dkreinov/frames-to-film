"""prompt_judge v2 — pre-render gate for Kling prompts.

Scores prompt-image alignment for the (image_a, image_b, prompt) tuple
that will be sent to Kling. Catches hallucinated/ungrounded prompts
before $0.084 of Kling spend.

v2 architecture (Phase 7.1.1, validated 2026-04-26):
- Same vendor-dispatch shape as clip_judge (qwen/gemini/moonshot)
- Default model: `qwen3-vl-plus` (~$0.005/call, ~6s, 5/6 on Olga set)
- Rubric emphasises grounding: "any concrete claim in the prompt that
  isn't visible in either image lowers the score"
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import requests

from backend.services.judges.base import JudgeScore, estimate_cost

DEFAULT_MODEL = "qwen3-vl-plus"

QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
MOONSHOT_BASE_URL = "https://api.moonshot.ai/v1"

_RUBRIC_HEAD = (
    "You are scoring a Kling AI video-generation prompt against the two "
    "source frames it will animate between (Image 1 = start frame, "
    "Image 2 = end frame).\n\n"
    "Rate prompt-image alignment 1-5 where:\n"
    "  5 = every concrete claim in the prompt (specific objects, places, "
    "motion) is grounded in what's visible in at least one of the images\n"
    "  4 = mostly grounded; minor stretch\n"
    "  3 = generic but not contradicted by the images\n"
    "  2 = describes things that aren't in either image, or contradicts them\n"
    "  1 = totally hallucinated; references missing subjects/objects/places\n\n"
    "Generic phrases like 'shimmering effect' alone don't justify a score "
    "above 3 unless the visible content matches.\n\n"
    "Respond with ONLY single-line JSON, no preamble, no markdown fence:\n"
    '{"score": <float 1-5>, "reasoning": "<one sentence>"}'
)


def _build_rubric(prompt_text: str) -> str:
    return f"{_RUBRIC_HEAD}\n\nPrompt to score:\n---\n{prompt_text}\n---"


def _img_data_uri(path: Path) -> str:
    b = base64.b64encode(path.read_bytes()).decode()
    ext = path.suffix.lower().lstrip(".") or "jpeg"
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{b}"


def _parse_response(text: str) -> tuple[float, str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
        if not m:
            raise ValueError(f"could not parse JSON from response: {text[:200]}")
        data = json.loads(m.group(0))
    score = float(data["score"])
    reasoning = str(data.get("reasoning", "")).strip()
    return score, reasoning


def _vendor_for_model(model: str) -> str:
    if model.startswith(("qwen", "qwen3")):
        return "qwen"
    if model.startswith("gemini"):
        return "gemini"
    if model.startswith("moonshot"):
        return "moonshot"
    raise ValueError(f"unknown model vendor for: {model}")


def _call_openai_compat_vision(
    *, base_url: str, key: str, model: str, rubric: str,
    image_a: Path, image_b: Path,
) -> tuple[str, int, int]:
    content: list[Any] = [
        {"type": "text", "text": rubric},
        {"type": "image_url", "image_url": {"url": _img_data_uri(image_a)}},
        {"type": "image_url", "image_url": {"url": _img_data_uri(image_b)}},
    ]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.0,
    }
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    in_tok = int(usage.get("prompt_tokens", 0) or 0)
    out_tok = int(usage.get("completion_tokens", 0) or 0)
    return text, in_tok, out_tok


def _call_gemini_vision(
    *, image_a: Path, image_b: Path, prompt_text: str, key: str, model: str,
) -> tuple[str, int, int]:
    """Lazy import; Gemini fallback path."""
    from google import genai
    from PIL import Image as PILImage

    client = genai.Client(**{"api_key": key})
    img_a = PILImage.open(image_a)
    img_b = PILImage.open(image_b)
    rubric = _build_rubric(prompt_text)
    resp = client.models.generate_content(
        model=model, contents=[rubric, img_a, img_b]
    )
    text = (resp.text or "").strip()
    usage = getattr(resp, "usage_metadata", None)
    in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
    out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
    return text, in_tok, out_tok


def _call_vision(
    *, model: str, image_a: Path, image_b: Path, prompt_text: str, key: str,
) -> tuple[str, int, int]:
    vendor = _vendor_for_model(model)
    if vendor == "qwen":
        return _call_openai_compat_vision(
            base_url=QWEN_BASE_URL, key=key, model=model,
            rubric=_build_rubric(prompt_text),
            image_a=image_a, image_b=image_b,
        )
    if vendor == "moonshot":
        return _call_openai_compat_vision(
            base_url=MOONSHOT_BASE_URL, key=key, model=model,
            rubric=_build_rubric(prompt_text),
            image_a=image_a, image_b=image_b,
        )
    if vendor == "gemini":
        return _call_gemini_vision(
            image_a=image_a, image_b=image_b,
            prompt_text=prompt_text, key=key, model=model,
        )
    raise ValueError(f"unsupported vendor: {vendor}")


def score_prompt(
    *,
    image_a: Path,
    image_b: Path,
    prompt_text: str,
    key: str,
    model: str = DEFAULT_MODEL,
) -> JudgeScore:
    """Score one (image_a, image_b, prompt) tuple. Returns JudgeScore.

    Failure mode: any error returns neutral 3.0 score; pipeline keeps
    going. Quality layer never blocks correctness.
    """
    try:
        text, in_tok, out_tok = _call_vision(
            model=model, image_a=image_a, image_b=image_b,
            prompt_text=prompt_text, key=key,
        )
        score, reasoning = _parse_response(text)
    except Exception as exc:
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
