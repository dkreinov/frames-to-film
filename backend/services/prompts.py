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
