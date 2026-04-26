"""clip_judge v2 — source-aware visual QA.

Inputs (Phase 7.1.1 v2 architecture, validated 2026-04-26 against Olga
real-asset test set):
- `source_start_path`: image_a fed to Kling for this pair (e.g. 33_b.jpg)
- `source_end_path`:   image_b fed to Kling for this pair (e.g. 34.jpg)
- `video_path`:        the rendered mp4 from Kling

Samples 3 frames at 0.2s, 2.5s, 4.5s; passes (source_start, source_end,
3 frames) to a vision LLM with the v2 rubric. Rubric flags ONLY
Kling-introduced artifacts; source-to-source differences are intentional
by design (life-montage = different photos / ages / scenes).

Default model: `qwen3-vl-plus` via Alibaba DashScope OpenAI-compatible
endpoint. ~$0.005/call, 5/6 correct on Olga validation. See
`docs/roadmap/phase_7_subplan_1_1_test_a2.md` for benchmark details.

Vendor dispatch is by model prefix:
  qwen* / qwen3*  → DashScope international endpoint, QWEEN_KEY
  gemini-*        → google-genai SDK, gemini env var
  moonshot-*      → Moonshot endpoint, KIMI_KEY
"""
from __future__ import annotations

import base64
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import requests

from backend.services.judges.base import JudgeScore, estimate_cost
from backend.services.judges.ffmpeg_utils import extract_frames_at_timestamps

DEFAULT_MODEL = "qwen3-vl-plus"
DEFAULT_TIMESTAMPS_S = [0.2, 2.5, 4.5]

QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
MOONSHOT_BASE_URL = "https://api.moonshot.ai/v1"

_RUBRIC_HEAD = (
    "You are auditing an AI-generated 5-second video clip from a real "
    "life-montage movie. You will receive 5 images IN ORDER:\n"
    "  Image 1: SOURCE START photo (frame fed to Kling as image_a)\n"
    "  Image 2: SOURCE END photo (frame fed to Kling as image_b)\n"
    "  Image 3: Clip frame at 0.2s (start of clip)\n"
    "  Image 4: Clip frame at 2.5s (middle of clip)\n"
    "  Image 5: Clip frame at 4.5s (end of clip)\n\n"
    "The clip interpolates between SOURCE START (Image 1) and SOURCE END "
    "(Image 2). Images 3-5 are what Kling rendered.\n\n"
    "This is a life-montage of one main character (a woman across years). "
    "The two source photos are taken at different times. They DIFFER "
    "intentionally — different outfits, settings, ages, supporting cast.\n\n"
    "DO NOT FLAG:\n"
    "- Differences between Image 1 and Image 2 (intentional — different photos)\n"
    "- Age progression of the main character\n"
    "- Supporting cast changes between sources\n\n"
    "DO FLAG ONLY (real Kling failures):\n"
    "- Main character drifting WITHIN the 3 clip frames (looking different "
    "across 0.2s/2.5s/4.5s in ways NOT explained by the source-to-source morph)\n"
    "- Text in clip becoming garbled when it was legible in source images "
    "(any script — Latin, Hebrew, Arabic, etc.)\n"
    "- Anatomy issues (missing arms, broken hands) in clip frames not in sources\n"
    "- Unnatural scary faces in clip output not in source faces\n"
    "- Heavy glitches/blur introduced by rendering\n"
    "- CONTENT HALLUCINATION: scenes / objects / people in the clip that "
    "are not present in EITHER source image (Kling inventing content)\n\n"
    "Score 1-5 (5 = no Kling-introduced issue, 1 = severe issue):\n"
    "  main_character_drift, text_artifacts, limb_anatomy, "
    "unnatural_faces, glitches, content_hallucination\n\n"
    "If issue is in source images themselves, do NOT count it.\n\n"
    "Respond with ONLY single-line JSON, no preamble, no markdown fence:\n"
    '{"main_character_drift": <1-5>, "text_artifacts": <1-5>, '
    '"limb_anatomy": <1-5>, "unnatural_faces": <1-5>, "glitches": <1-5>, '
    '"content_hallucination": <1-5>, "specific_issues": "<sentence>"}'
)


def _build_rubric() -> str:
    return _RUBRIC_HEAD


def _img_data_uri(path: Path) -> str:
    b = base64.b64encode(path.read_bytes()).decode()
    ext = path.suffix.lower().lstrip(".") or "jpeg"
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{b}"


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


def _vendor_for_model(model: str) -> str:
    if model.startswith(("qwen", "qwen3")):
        return "qwen"
    if model.startswith("gemini"):
        return "gemini"
    if model.startswith("moonshot"):
        return "moonshot"
    raise ValueError(f"unknown model vendor for: {model}")


def _call_openai_compat_vision(
    *,
    base_url: str,
    key: str,
    model: str,
    rubric: str,
    image_paths: list[Path],
) -> tuple[str, int, int]:
    """Vendor-agnostic OpenAI-compatible chat completion with images."""
    content: list[Any] = [{"type": "text", "text": rubric}]
    for p in image_paths:
        content.append({"type": "image_url", "image_url": {"url": _img_data_uri(p)}})
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.0,
    }
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    in_tok = int(usage.get("prompt_tokens", 0) or 0)
    out_tok = int(usage.get("completion_tokens", 0) or 0)
    return text, in_tok, out_tok


def _call_gemini_vision(
    *,
    rubric: str,
    image_paths: list[Path],
    key: str,
    model: str,
) -> tuple[str, int, int]:
    """Gemini fallback path. Lazy import."""
    from google import genai
    from PIL import Image as PILImage

    client = genai.Client(**{"api_key": key})
    images = [PILImage.open(p) for p in image_paths]
    resp = client.models.generate_content(
        model=model, contents=[rubric, *images]
    )
    text = (resp.text or "").strip()
    usage = getattr(resp, "usage_metadata", None)
    in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
    out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
    return text, in_tok, out_tok


def _call_vision(
    *,
    model: str,
    rubric: str,
    image_paths: list[Path],
    key: str,
) -> tuple[str, int, int]:
    """Dispatch to the right vendor based on model prefix."""
    vendor = _vendor_for_model(model)
    if vendor == "qwen":
        return _call_openai_compat_vision(
            base_url=QWEN_BASE_URL, key=key, model=model,
            rubric=rubric, image_paths=image_paths,
        )
    if vendor == "moonshot":
        return _call_openai_compat_vision(
            base_url=MOONSHOT_BASE_URL, key=key, model=model,
            rubric=rubric, image_paths=image_paths,
        )
    if vendor == "gemini":
        return _call_gemini_vision(
            rubric=rubric, image_paths=image_paths, key=key, model=model,
        )
    raise ValueError(f"unsupported vendor: {vendor}")


def _neutral_fallback(model: str, reason: str) -> JudgeScore:
    return JudgeScore(
        judge="clip_judge",
        scores={
            "main_character_drift": 3.0,
            "text_artifacts": 3.0,
            "limb_anatomy": 3.0,
            "unnatural_faces": 3.0,
            "glitches": 3.0,
            "content_hallucination": 3.0,
        },
        reasoning=reason,
        model_used=model,
    )


def score_clip(
    *,
    video_path: Path,
    source_start_path: Path,
    source_end_path: Path,
    key: str,
    model: str = DEFAULT_MODEL,
    timestamps_s: list[float] | None = None,
    frame_dir: Path | None = None,
) -> JudgeScore:
    """Score a 5s clip via source-aware v2 judge.

    Args:
        video_path: rendered Kling clip mp4
        source_start_path: image_a fed to Kling for this pair
        source_end_path:   image_b fed to Kling for this pair
        key: API key for the chosen model's vendor
        model: judge model (default qwen3-vl-plus)
        timestamps_s: frame sampling points (default 0.2, 2.5, 4.5)
        frame_dir: optional persistent dir for extracted frames

    Returns JudgeScore with 6 dimensions per the v2 rubric. On any
    failure (extraction, network, parse), returns a neutral 3.0
    fallback — pipeline correctness is never blocked.
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
        except Exception as exc:
            return _neutral_fallback(model, f"frame extraction failed: {exc!r}")

        # Order matters: source_start, source_end, frame_0.2, frame_2.5, frame_4.5
        all_images = [source_start_path, source_end_path, *frames]

        try:
            text, in_tok, out_tok = _call_vision(
                model=model, rubric=_build_rubric(),
                image_paths=all_images, key=key,
            )
            data = _parse_response(text)
        except Exception as exc:
            return _neutral_fallback(model, f"judge call failed: {exc!r}")

        scores: dict[str, Any] = {}
        for k in (
            "main_character_drift", "text_artifacts", "limb_anatomy",
            "unnatural_faces", "glitches", "content_hallucination",
        ):
            try:
                scores[k] = float(data.get(k, 3.0))
            except (TypeError, ValueError):
                scores[k] = 3.0

        return JudgeScore(
            judge="clip_judge",
            scores=scores,
            reasoning=str(data.get("specific_issues", "")).strip(),
            model_used=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=estimate_cost(model, in_tok, out_tok),
        )
    finally:
        if tmp is not None:
            tmp.cleanup()
