"""Transition-aware prompt writer — Phase 7.5 (Stream A).

Per-pair Kling prompt builder. Takes:
- image_a, image_b: the two source frames Kling will animate between
- pair_intent: from story.py output ({from, to, device, intent})
- arc_type: which story arc this clip belongs to (drives camera_language)
- key: API key for the chosen vendor

Reads:
- data/cinematic_devices.yaml — looks up the device by id, gets the
  prompt_template, applicable_arcs, etc.
- data/story_arcs/{arc_type}.yaml — gets camera_language guidance
- data/kling_prompt_rules.yaml — forbidden phrases, allowed movements,
  multi-shot rules, etc.

Calls a vision LLM with all this context + the two source images,
returns a single Kling-ready prompt string.

Architecture mirrors story.py: vendor dispatch by model prefix,
default qwen3-vl-plus, neutral fallback on errors.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import requests
import yaml

from backend.services.judges.base import estimate_cost

DEFAULT_MODEL = "qwen3-vl-plus"

QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
MOONSHOT_BASE_URL = "https://api.moonshot.ai/v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCS_DIR = REPO_ROOT / "data" / "story_arcs"
DEVICES_PATH = REPO_ROOT / "data" / "cinematic_devices.yaml"
KLING_RULES_PATH = REPO_ROOT / "data" / "kling_prompt_rules.yaml"

_FALLBACK_PROMPT = (
    "Smooth dolly forward; preserve the subject's identity and the "
    "scene's lighting between source frames."
)


# --- catalog loaders -------------------------------------------------

def _load_arc_template(arc_type: str) -> dict[str, Any]:
    candidates = [arc_type, arc_type.replace("-", "_"),
                  arc_type.replace("_", "-")]
    for slug in candidates:
        p = ARCS_DIR / f"{slug}.yaml"
        if p.is_file():
            return yaml.safe_load(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"unknown arc_type {arc_type!r}")


def _load_devices_catalog() -> list[dict[str, Any]]:
    if not DEVICES_PATH.is_file():
        raise FileNotFoundError(f"missing {DEVICES_PATH}")
    return yaml.safe_load(DEVICES_PATH.read_text(encoding="utf-8")) or []


def _load_kling_rules() -> dict[str, Any]:
    if not KLING_RULES_PATH.is_file():
        return {}
    return yaml.safe_load(KLING_RULES_PATH.read_text(encoding="utf-8")) or {}


def _find_device(catalog: list[dict[str, Any]], device_id: str) -> dict[str, Any]:
    for d in catalog:
        if d.get("id") == device_id:
            return d
    raise KeyError(
        f"device {device_id!r} not in catalog "
        f"(known: {[d['id'] for d in catalog]})"
    )


# --- rubric ----------------------------------------------------------

def _build_rubric(
    *,
    device: dict[str, Any],
    arc: dict[str, Any],
    kling_rules: dict[str, Any],
    pair_intent: dict[str, Any],
) -> str:
    forbidden = kling_rules.get("forbidden_phrases", [])
    forbidden_str = ", ".join(forbidden[:8])
    movements = kling_rules.get("camera_vocabulary", {}).get("movements", [])
    movement_ids = ", ".join(m["id"] for m in movements)
    word_budget = kling_rules.get("word_budget", {})
    word_min = word_budget.get("ideal_min", 30)
    word_max = word_budget.get("ideal_max", 60)

    return (
        "You are writing a single Kling AI image-to-video prompt for one "
        "pair of source frames. The clip will interpolate from image A "
        "to image B.\n\n"
        f"Story arc: {arc.get('name')} ({arc.get('id')})\n"
        f"Camera language guidance for this arc:\n"
        f"{arc.get('camera_language', '').strip()}\n\n"
        f"Cinematic device chosen for this pair: {device.get('name')} "
        f"({device.get('id')})\n"
        f"Device description: {device.get('description', '').strip()}\n"
        f"Device prompt_template (use as a starting point, "
        f"fill placeholders from what you see in images):\n"
        f"{device.get('prompt_template', '').strip()}\n\n"
        f"Per-pair motion intent (what the story writer said this clip "
        f"should accomplish):\n  {pair_intent.get('intent', '')}\n\n"
        f"KLING PROMPT RULES — STRICT:\n"
        f"  - Do NOT redescribe what's in the images. Only describe motion.\n"
        f"  - Open with HOW the shot is captured (camera vocabulary).\n"
        f"  - ONE primary motion + at most one secondary motion.\n"
        f"  - Sequential: 'then', 'and then' — never stacked summaries.\n"
        f"  - Word budget: {word_min}-{word_max} words ideal.\n"
        f"  - Allowed camera vocabulary IDs: {movement_ids}.\n"
        f"  - Avoid these forbidden generic phrases: {forbidden_str}.\n"
        f"  - Don't use 'cinematic' / 'beautiful' / 'high quality' / "
        f"'4K' / 'masterpiece' — Kling 3.0 explicitly ignores these.\n\n"
        f"Look at the two source images and write ONE Kling prompt that "
        f"applies the chosen device, follows the arc camera language, "
        f"and respects all the rules above.\n\n"
        f"Respond with ONLY the prompt text — no preamble, no quotes, "
        f"no markdown."
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
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json=payload, timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return text, int(usage.get("prompt_tokens", 0) or 0), \
        int(usage.get("completion_tokens", 0) or 0)


def _call_gemini_vision(
    *, image_a: Path, image_b: Path, rubric: str, key: str, model: str,
) -> tuple[str, int, int]:
    from google import genai
    from PIL import Image as PILImage

    client = genai.Client(**{"api_key": key})
    img_a = PILImage.open(image_a)
    img_b = PILImage.open(image_b)
    resp = client.models.generate_content(
        model=model, contents=[rubric, img_a, img_b]
    )
    text = (resp.text or "").strip()
    usage = getattr(resp, "usage_metadata", None)
    return text, int(getattr(usage, "prompt_token_count", 0) or 0), \
        int(getattr(usage, "candidates_token_count", 0) or 0)


def _call_vision(
    *, model: str, rubric: str, image_a: Path, image_b: Path, key: str,
) -> tuple[str, int, int]:
    vendor = _vendor_for_model(model)
    if vendor == "qwen":
        return _call_openai_compat(
            base_url=QWEN_BASE_URL, key=key, model=model,
            rubric=rubric, image_a=image_a, image_b=image_b,
        )
    if vendor == "moonshot":
        return _call_openai_compat(
            base_url=MOONSHOT_BASE_URL, key=key, model=model,
            rubric=rubric, image_a=image_a, image_b=image_b,
        )
    if vendor == "gemini":
        return _call_gemini_vision(
            image_a=image_a, image_b=image_b, rubric=rubric,
            key=key, model=model,
        )
    raise ValueError(f"unsupported vendor: {vendor}")


# --- public API ------------------------------------------------------

def write_prompt(
    *,
    image_a: Path,
    image_b: Path,
    pair_intent: dict[str, Any],
    arc_type: str,
    key: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Return a single Kling-ready prompt string for this pair.

    Raises FileNotFoundError if `arc_type` doesn't map to a YAML.
    Raises KeyError if pair_intent['device'] isn't in the catalog.
    All other errors return a neutral fallback prompt — pipeline never
    blocked.
    """
    arc = _load_arc_template(arc_type)
    catalog = _load_devices_catalog()
    device = _find_device(catalog, pair_intent.get("device", ""))
    kling_rules = _load_kling_rules()

    rubric = _build_rubric(
        device=device, arc=arc, kling_rules=kling_rules,
        pair_intent=pair_intent,
    )

    try:
        text, _in_tok, _out_tok = _call_vision(
            model=model, rubric=rubric,
            image_a=image_a, image_b=image_b, key=key,
        )
    except Exception:
        # Neutral fallback. Pipeline always has SOMETHING to send to Kling.
        return _FALLBACK_PROMPT

    return text.strip() or _FALLBACK_PROMPT
