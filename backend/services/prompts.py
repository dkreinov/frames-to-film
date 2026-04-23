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


def _pair_keys_for_project(project_dir: Path) -> list[str]:
    img_dir = project_dir / "kling_test"
    if not img_dir.is_dir():
        raise FileNotFoundError(f"kling_test dir missing: {img_dir}")
    frames = sorted(img_dir.glob("*.jpg"), key=lambda p: _sort_key(p.name))
    if len(frames) < 2:
        raise FileNotFoundError(f"need >=2 jpgs in {img_dir}, got {len(frames)}")
    return [f"{a.stem}_to_{b.stem}" for a, b in zip(frames, frames[1:])]


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
