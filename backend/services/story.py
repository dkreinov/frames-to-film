"""story-writer service — Phase 7.4 (Stream A).

Top-level call sees all source images + an arc template + the operator's
brief, returns a structured StoryDoc with arc paragraph + per-pair
motion intents.

Architecture mirrors `clip_judge.py`: vendor dispatch by model prefix
(qwen / gemini / moonshot), default `qwen3-vl-plus` (cheapest source-aware
vision per Phase 7.1.1 v2 benchmark).

Inputs:
- `image_paths`: list of N source frame paths (in render order)
- `brief`: operator's subject + tone + notes
- `arc_type`: one of life-montage, 3-act-heroic, travel-diary,
  event-recap, day-in-life (must match a YAML in `data/story_arcs/`)
- `key`: API key for the chosen vendor
- `model`: optional override (default `qwen3-vl-plus`)

Output: `StoryDoc` (Pydantic) with `arc_paragraph` + `pair_intents` +
token + cost telemetry.

Failure mode: any error returns a neutral StoryDoc with a fallback
arc_paragraph and empty pair_intents — pipeline correctness never blocked.
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import requests
import yaml
from pydantic import BaseModel, Field

from backend.services.judges.base import estimate_cost

DEFAULT_MODEL = "qwen3-vl-plus"

QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
MOONSHOT_BASE_URL = "https://api.moonshot.ai/v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCS_DIR = REPO_ROOT / "data" / "story_arcs"
KLING_RULES_PATH = REPO_ROOT / "data" / "kling_prompt_rules.yaml"


# --- output shape ----------------------------------------------------

class PairIntent(BaseModel):
    """One per consecutive image pair."""
    from_: int = Field(alias="from")
    to: int
    device: str  # cinematic_devices.yaml id
    intent: str  # one-sentence motion description

    model_config = {"populate_by_name": True}


class StoryDoc(BaseModel):
    """Full story-writer output. Persists to story.json."""
    arc_paragraph: str
    pair_intents: list[dict[str, Any]] = Field(default_factory=list)
    arc_type: str | None = None
    reasoning: str = ""
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


# --- arc + rules loading ---------------------------------------------

def _load_arc_template(arc_type: str) -> dict[str, Any]:
    """Load `data/story_arcs/{arc_type}.yaml`. The arc_type in the YAML
    files uses snake_case (life_montage), but operator-facing strings
    use hyphens (life-montage). Normalize both directions.
    """
    candidates = [
        arc_type,
        arc_type.replace("-", "_"),
        arc_type.replace("_", "-"),
    ]
    for slug in candidates:
        p = ARCS_DIR / f"{slug}.yaml"
        if p.is_file():
            return yaml.safe_load(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        f"unknown arc_type {arc_type!r} (looked for "
        f"{[str(ARCS_DIR / f'{c}.yaml') for c in candidates]})"
    )


def _load_kling_rules() -> dict[str, Any]:
    if not KLING_RULES_PATH.is_file():
        return {}
    return yaml.safe_load(KLING_RULES_PATH.read_text(encoding="utf-8")) or {}


def _build_rubric(
    *,
    arc: dict[str, Any],
    kling_rules: dict[str, Any],
    brief: dict[str, Any],
    n_images: int,
) -> str:
    """Build the LLM prompt that will produce the StoryDoc JSON."""
    n_pairs = max(0, n_images - 1)
    forbidden = ", ".join(kling_rules.get("forbidden_phrases", [])[:8])
    allowed_movements = ", ".join(
        m["id"] for m in kling_rules.get("camera_vocabulary", {}).get("movements", [])
    )
    transitions_preferred = ", ".join(arc.get("transitions_preferred", []))

    return (
        f"You are the story writer for an AI life-montage video. The "
        f"operator uploaded {n_images} source photos in chronological "
        f"order. Your job: write a 3-paragraph arc paragraph that ties "
        f"them together, AND list one motion intent per consecutive "
        f"pair ({n_pairs} pairs total).\n\n"
        f"Arc type: {arc.get('id')} ({arc.get('name')})\n"
        f"Continuity rule: {arc.get('continuity_rule', '').strip()}\n"
        f"Pacing: {arc.get('pacing')}\n"
        f"Camera language guidance:\n{arc.get('camera_language', '').strip()}\n"
        f"Preferred transitions for this arc: {transitions_preferred}\n\n"
        f"Operator brief:\n"
        f"  Subject: {brief.get('subject', '')}\n"
        f"  Tone: {brief.get('tone', '')}\n"
        f"  Notes: {brief.get('notes', '')}\n\n"
        f"Story-writer extra instructions for this arc:\n"
        f"{arc.get('story_writer_extra_instructions', '').strip()}\n\n"
        f"KLING PROMPT RULES (motion is what you write, not redescription):\n"
        f"  - Do NOT redescribe what's in the images. Only describe motion.\n"
        f"  - Each pair_intent is ONE camera motion + ONE primary action.\n"
        f"  - Prefer these camera vocabulary IDs: {allowed_movements}.\n"
        f"  - DO NOT use these forbidden generic phrases: {forbidden}.\n"
        f"  - Each pair_intent.intent should be 1-2 short sentences.\n\n"
        f"Pick a `device` for each pair from the preferred-transitions "
        f"list above (or any valid catalog id like cross_dissolve, "
        f"age_match_cut, photo_frame, iris_in, etc.).\n\n"
        f"Respond with ONLY single JSON object, no preamble, no markdown:\n"
        f'{{"arc_paragraph": "<3 paragraphs>", '
        f'"pair_intents": [{{"from": 1, "to": 2, "device": "<id>", '
        f'"intent": "<motion>"}}, ...]}}'
    )


# --- vendor dispatch -------------------------------------------------

def _vendor_for_model(model: str) -> str:
    if model.startswith(("qwen", "qwen3")):
        return "qwen"
    if model.startswith("gemini"):
        return "gemini"
    if model.startswith("moonshot"):
        return "moonshot"
    raise ValueError(f"unknown model vendor for: {model}")


def _img_data_uri(path: Path) -> str:
    b = base64.b64encode(path.read_bytes()).decode()
    ext = path.suffix.lower().lstrip(".") or "jpeg"
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{b}"


def _call_openai_compat(
    *, base_url: str, key: str, model: str, rubric: str,
    image_paths: list[Path],
) -> tuple[str, int, int]:
    content: list[Any] = [{"type": "text", "text": rubric}]
    for p in image_paths:
        content.append({"type": "image_url",
                        "image_url": {"url": _img_data_uri(p)}})
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.0,
    }
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json=payload, timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return text, int(usage.get("prompt_tokens", 0) or 0), \
        int(usage.get("completion_tokens", 0) or 0)


def _call_gemini_vision(
    *, rubric: str, image_paths: list[Path], key: str, model: str,
) -> tuple[str, int, int]:
    from google import genai
    from PIL import Image as PILImage

    client = genai.Client(**{"api_key": key})
    images = [PILImage.open(p) for p in image_paths]
    resp = client.models.generate_content(
        model=model, contents=[rubric, *images]
    )
    text = (resp.text or "").strip()
    usage = getattr(resp, "usage_metadata", None)
    return text, int(getattr(usage, "prompt_token_count", 0) or 0), \
        int(getattr(usage, "candidates_token_count", 0) or 0)


def _call_vision(
    *, model: str, rubric: str, image_paths: list[Path], key: str,
) -> tuple[str, int, int]:
    """Dispatch to the right vendor based on model prefix."""
    vendor = _vendor_for_model(model)
    if vendor == "qwen":
        return _call_openai_compat(
            base_url=QWEN_BASE_URL, key=key, model=model,
            rubric=rubric, image_paths=image_paths,
        )
    if vendor == "moonshot":
        return _call_openai_compat(
            base_url=MOONSHOT_BASE_URL, key=key, model=model,
            rubric=rubric, image_paths=image_paths,
        )
    if vendor == "gemini":
        return _call_gemini_vision(
            rubric=rubric, image_paths=image_paths, key=key, model=model,
        )
    raise ValueError(f"unsupported vendor: {vendor}")


# --- response parsing ------------------------------------------------

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


# --- public API ------------------------------------------------------

def write_story(
    *,
    image_paths: list[Path],
    brief: dict[str, Any],
    arc_type: str,
    key: str,
    model: str = DEFAULT_MODEL,
) -> StoryDoc:
    """Write the full story for a project. See module docstring.

    Raises FileNotFoundError if `arc_type` doesn't map to a YAML in
    `data/story_arcs/`. All other errors fall back to a neutral
    StoryDoc so the pipeline keeps moving.
    """
    arc = _load_arc_template(arc_type)
    kling_rules = _load_kling_rules()
    rubric = _build_rubric(
        arc=arc, kling_rules=kling_rules, brief=brief,
        n_images=len(image_paths),
    )

    try:
        text, in_tok, out_tok = _call_vision(
            model=model, rubric=rubric, image_paths=image_paths, key=key,
        )
        data = _parse_response(text)
    except Exception as exc:
        return StoryDoc(
            arc_paragraph="(story-writer error; pipeline continued with "
                          "fallback empty arc)",
            pair_intents=[],
            arc_type=arc_type,
            reasoning=f"story error (fallback): {exc!r}",
            model_used=model,
        )

    return StoryDoc(
        arc_paragraph=str(data.get("arc_paragraph", "")).strip(),
        pair_intents=list(data.get("pair_intents", [])),
        arc_type=arc_type,
        reasoning="",
        model_used=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=estimate_cost(model, in_tok, out_tok),
    )
