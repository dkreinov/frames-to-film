"""Prompt generation + resolution service.

Replaces the Olga-specific `PAIR_PROMPTS` + `FALLBACK_PROMPT` pattern with:

1. A small set of generic **style presets** (cinematic, nostalgic, vintage, playful)
   — each is a short camera-first description, De-Olga'd (no "childhood B&W studio",
   no "wedding chuppah", etc.).
2. A **resolver** that picks the best available prompt in precedence:
   project `prompts.json` > style preset > generic fallback.
3. Two **generators** (mock + api) that populate `<project>/prompts.json` from
   the pairs discovered in `<project>/kling_test/*.jpg`.

For the Olga backward-compat path, `generate_all_videos.py` keeps importing
`PAIR_PROMPTS` from `image_pair_prompts.py` — nothing in this module overrides
that. Phase 6 retires it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FALLBACK_PROMPT = (
    "Gentle push-in. Transition naturally between the two source frames. "
    "Preserve the same setting, lighting continuity, and photographic style."
)

STYLE_PRESETS: dict[str, str] = {
    "cinematic": (
        "Slow cinematic dolly. Transition smoothly between the two source frames. "
        "Preserve the composition, lighting, and photographic style continuously."
    ),
    "nostalgic": (
        "Slow lateral drift. Transition gently between the two source frames. "
        "Preserve soft warm lighting and a quiet reflective mood."
    ),
    "vintage": (
        "Gentle dolly with slight handheld sway. Transition organically between "
        "the two source frames. Preserve film grain, muted colors, and a period "
        "photographic feel."
    ),
    "playful": (
        "Light push-in with subtle energy. Transition briskly between the two "
        "source frames. Preserve bright saturated colors and an upbeat mood."
    ),
}


def resolve_prompt(
    pair_key: str,
    project_dir: Path | str | None,
    style: str = "cinematic",
    fallback: str = FALLBACK_PROMPT,
) -> str:
    """Resolve a single prompt.

    Precedence:
        1. `<project_dir>/prompts.json` keyed by pair_key
        2. STYLE_PRESETS[style]
        3. fallback
    """
    if project_dir is not None:
        pj = Path(project_dir) / "prompts.json"
        if pj.is_file():
            try:
                data = json.loads(pj.read_text())
                if pair_key in data and isinstance(data[pair_key], str):
                    return data[pair_key]
            except (json.JSONDecodeError, OSError):
                pass  # fall through
    return STYLE_PRESETS.get(style, fallback)


def _sort_key(filename: str) -> tuple[int, str]:
    base = filename.split(".")[0]
    m = re.match(r"^(\d+)(_([a-z]))?$", base)
    if m:
        return (int(m.group(1)), m.group(3) or "")
    return (9999, base)


def _load_order(project_dir: Path) -> list[str] | None:
    """Return the Storyboard-saved order (Phase 4 sub-plan 3) if present.
    Mirrors backend/services/generate.py::_load_order so prompts + videos
    use the same precedence rule."""
    pj = project_dir / "order.json"
    if not pj.is_file():
        return None
    try:
        data = json.loads(pj.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    raw = data.get("order")
    if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
        return raw
    return None


def _pair_keys_for_project(project_dir: Path) -> list[str]:
    img_dir = project_dir / "kling_test"
    if not img_dir.is_dir():
        raise FileNotFoundError(f"kling_test dir missing: {img_dir}")
    all_frames = sorted(img_dir.glob("*.jpg"), key=lambda p: _sort_key(p.name))
    if len(all_frames) < 2:
        raise FileNotFoundError(f"need >=2 jpgs in {img_dir}, got {len(all_frames)}")

    # Prefer the Storyboard-saved order, filtered to frames that still
    # exist on disk. Fall back to numeric sort if order.json is absent
    # or references only missing files.
    explicit = _load_order(project_dir)
    if explicit:
        existing = {p.name: p for p in all_frames}
        ordered = [existing[name] for name in explicit if name in existing]
        if len(ordered) >= 2:
            return [f"{a.stem}_to_{b.stem}" for a, b in zip(ordered, ordered[1:])]

    return [f"{a.stem}_to_{b.stem}" for a, b in zip(all_frames, all_frames[1:])]


def generate_prompts_mock(project_dir: Path | str, style: str = "cinematic") -> dict[str, str]:
    """Mock generator — writes prompts.json using the chosen style preset.

    Every pair gets the same preset string (no per-image variation). Good
    enough for CI + offline dev. No network, no API key required.
    """
    project_dir = Path(project_dir)
    pairs = _pair_keys_for_project(project_dir)
    preset = STYLE_PRESETS.get(style, FALLBACK_PROMPT)
    out = {k: preset for k in pairs}
    (project_dir / "prompts.json").write_text(json.dumps(out, indent=2))
    return out


GEMINI_MODEL = "gemini-2.0-flash"

_API_PROMPT_TEMPLATE = (
    "You are writing a single short cinematic prompt for a Kling AI image-to-video "
    "transition between two consecutive frames. The chosen style is '{style}'.\n"
    "Write 1-3 sentences. Describe the camera move first, then the transition "
    "behavior, then any scene/lighting continuity to preserve.\n"
    "Do NOT invent new people or objects. Do NOT reference the original family, "
    "any names, or any specific personal details. Keep it generic and reusable.\n"
    "Return only the prompt text — no preamble, no quotes, no markdown."
)


def _get_genai_client(key: str) -> Any:
    """Thin wrapper — replaced by tests. Import lazily so offline tests
    never need the google-genai SDK loaded.

    Accepts the key explicitly so the resolver (header -> env) lives in
    backend/deps.py::get_gemini_key, not scattered across services.
    """
    from google import genai
    return genai.Client(**{"api_key": key})


def generate_prompts_api(
    project_dir: Path | str,
    style: str = "cinematic",
    key: str = "",
) -> dict[str, str]:
    """API generator — calls gemini-2.0-flash per pair with both frame images
    + a style hint. On any per-pair API error, falls back to the style preset
    for that pair so the output dict is always complete.

    `key` is the resolved Gemini API key from backend.deps.get_gemini_key.
    Callers must pass it; the service no longer reads env directly.
    """
    project_dir = Path(project_dir)
    pairs = _pair_keys_for_project(project_dir)
    img_dir = project_dir / "kling_test"
    preset = STYLE_PRESETS.get(style, FALLBACK_PROMPT)

    client = _get_genai_client(key)
    instruction = _API_PROMPT_TEMPLATE.format(style=style)
    out: dict[str, str] = {}

    from PIL import Image
    for pair_key in pairs:
        a_stem, b_stem = pair_key.split("_to_")
        img_a = Image.open(img_dir / f"{a_stem}.jpg")
        img_b = Image.open(img_dir / f"{b_stem}.jpg")
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[instruction, img_a, img_b],
            )
            text = (resp.text or "").strip()
            out[pair_key] = text or preset
        except Exception:  # fall back per-pair; don't lose the whole run
            out[pair_key] = preset

    (project_dir / "prompts.json").write_text(json.dumps(out, indent=2))
    return out


def prompts_runner(**payload) -> dict:
    """Adapter for backend.services.jobs.run_job_sync.

    Expects `gemini_key` in payload when mode == "api" (resolved by the
    HTTP handler's get_gemini_key dependency and written into the job
    payload so the background runner doesn't need request context).
    """
    project_dir = Path(payload["project_dir"])
    mode = payload.get("mode", "mock")
    style = payload.get("style", "cinematic")
    if mode == "mock":
        produced = generate_prompts_mock(project_dir, style=style)
    elif mode == "api":
        key = payload.get("gemini_key") or ""
        produced = generate_prompts_api(project_dir, style=style, key=key)
    else:
        raise ValueError(f"unknown mode: {mode}")
    return {"produced": list(produced.keys())}
