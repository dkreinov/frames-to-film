"""Step 2: style preset library + resolve_prompt contract (TDD red).

Precedence: project prompts.json > style preset > fallback.
STYLE_PRESETS exposes 4 keys: cinematic, nostalgic, vintage, playful.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.prompts import (
    STYLE_PRESETS,
    FALLBACK_PROMPT,
    resolve_prompt,
)


def test_style_presets_expose_four_keys() -> None:
    assert set(STYLE_PRESETS.keys()) == {"cinematic", "nostalgic", "vintage", "playful"}
    for preset in STYLE_PRESETS.values():
        assert isinstance(preset, str) and len(preset) > 20


def test_resolver_prefers_project_json(tmp_path: Path) -> None:
    (tmp_path / "prompts" / "prompts.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "prompts" / "prompts.json").write_text(json.dumps({"1_to_2": "CUSTOM PROMPT"}))
    result = resolve_prompt("1_to_2", project_dir=tmp_path, style="cinematic")
    assert result == "CUSTOM PROMPT"


def test_resolver_falls_back_to_style_preset(tmp_path: Path) -> None:
    # no prompts.json written
    result = resolve_prompt("99_to_100", project_dir=tmp_path, style="nostalgic")
    assert result == STYLE_PRESETS["nostalgic"]


def test_resolver_falls_back_to_generic_when_style_unknown(tmp_path: Path) -> None:
    result = resolve_prompt("99_to_100", project_dir=tmp_path, style="not-a-style")
    assert result == FALLBACK_PROMPT


def test_resolver_handles_missing_project_dir() -> None:
    # None or non-existent dir -> style preset, not crash
    result = resolve_prompt("1_to_2", project_dir=None, style="playful")
    assert result == STYLE_PRESETS["playful"]
