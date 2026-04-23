"""Step 3: generate_prompts_mock (TDD red).

Scans <project>/kling_test/*.jpg, orders numerically, builds pair keys
(1_to_2, 2_to_3, ...), writes <project>/prompts.json using STYLE_PRESETS.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.prompts import (
    STYLE_PRESETS,
    generate_prompts_mock,
)


def _seed_kling(dir_: Path, count: int) -> None:
    d = dir_ / "kling_test"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        (d / f"{i}.jpg").write_bytes(b"\xff\xd8\xff\xe0")


def test_mock_produces_n_minus_1_pairs_for_n_frames(tmp_path: Path) -> None:
    _seed_kling(tmp_path, 6)
    out = generate_prompts_mock(tmp_path, style="cinematic")
    assert set(out.keys()) == {"1_to_2", "2_to_3", "3_to_4", "4_to_5", "5_to_6"}
    # Each prompt must match the cinematic preset exactly.
    for v in out.values():
        assert v == STYLE_PRESETS["cinematic"]
    # prompts.json written
    saved = json.loads((tmp_path / "prompts.json").read_text())
    assert saved == out


def test_mock_uses_nostalgic_preset_when_requested(tmp_path: Path) -> None:
    _seed_kling(tmp_path, 3)
    out = generate_prompts_mock(tmp_path, style="nostalgic")
    for v in out.values():
        assert v == STYLE_PRESETS["nostalgic"]


def test_mock_errors_when_kling_dir_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        generate_prompts_mock(tmp_path, style="cinematic")
