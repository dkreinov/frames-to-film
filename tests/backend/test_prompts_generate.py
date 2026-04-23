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
    from PIL import Image
    d = dir_ / "kling_test"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        Image.new("RGB", (16, 16), (i * 30, 0, 0)).save(d / f"{i}.jpg", "JPEG")


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


# --- Step 4: API generator (Gemini flash) ---

def _seed_kling_with_jpgs(dir_: Path, count: int) -> None:
    _seed_kling(dir_, count)


def test_api_generator_calls_gemini_once_per_pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """6 frames -> 5 pairs -> 5 Gemini calls. Output dict keys match pair keys."""
    from backend.services import prompts as prompts_mod
    _seed_kling(tmp_path, 6)

    calls: list[dict] = []

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeModels:
        def generate_content(self, *, model, contents, **_ignored):
            calls.append({"model": model, "contents": contents})
            return FakeResponse(f"generated-prompt-{len(calls)}")

    class FakeClient:
        def __init__(self) -> None:
            self.models = FakeModels()

    monkeypatch.setattr(prompts_mod, "_get_genai_client", lambda: FakeClient())

    out = prompts_mod.generate_prompts_api(tmp_path, style="cinematic")
    assert set(out.keys()) == {"1_to_2", "2_to_3", "3_to_4", "4_to_5", "5_to_6"}
    # 5 API calls, each using the flash model
    assert len(calls) == 5
    assert all(c["model"] == "gemini-2.0-flash" for c in calls)
    # generated prompts persisted
    saved = json.loads((tmp_path / "prompts.json").read_text())
    assert saved == out


# --- Phase 4 sub-plan 4 Step 1: pair_keys honour order.json ---

def test_pair_keys_use_numeric_sort_when_no_order_json(tmp_path: Path) -> None:
    """Without order.json, fall back to numeric-stem sort (existing behaviour)."""
    from backend.services.prompts import _pair_keys_for_project

    _seed_kling(tmp_path, 3)
    assert _pair_keys_for_project(tmp_path) == ["1_to_2", "2_to_3"]


def test_pair_keys_honour_order_json_when_present(tmp_path: Path) -> None:
    """With order.json, pair_keys follow the saved order (not numeric sort)."""
    from backend.services.prompts import _pair_keys_for_project

    _seed_kling(tmp_path, 3)
    (tmp_path / "order.json").write_text(
        json.dumps({"order": ["3.jpg", "1.jpg", "2.jpg"]})
    )
    assert _pair_keys_for_project(tmp_path) == ["3_to_1", "1_to_2"]


def test_pair_keys_fall_back_when_order_references_missing_files(tmp_path: Path) -> None:
    """If order.json references frames that no longer exist, drop them and
    fall back to numeric sort if nothing valid remains."""
    from backend.services.prompts import _pair_keys_for_project

    _seed_kling(tmp_path, 3)
    (tmp_path / "order.json").write_text(
        json.dumps({"order": ["ghost.jpg", "also-ghost.jpg"]})
    )
    # All referenced files are missing -> fall back to numeric sort.
    assert _pair_keys_for_project(tmp_path) == ["1_to_2", "2_to_3"]


def test_mock_generator_pairs_follow_order_json(tmp_path: Path) -> None:
    """End-to-end: writing order.json before mock-gen yields prompts.json
    keyed by the reordered pair_keys."""
    _seed_kling(tmp_path, 4)
    (tmp_path / "order.json").write_text(
        json.dumps({"order": ["4.jpg", "2.jpg", "1.jpg", "3.jpg"]})
    )
    out = generate_prompts_mock(tmp_path, style="cinematic")
    assert list(out.keys()) == ["4_to_2", "2_to_1", "1_to_3"]


def test_api_generator_falls_back_to_preset_on_api_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If a Gemini call raises, the resolver falls back to the style preset for that pair."""
    from backend.services import prompts as prompts_mod
    _seed_kling(tmp_path, 3)

    class FakeModels:
        def generate_content(self, **kwargs):
            raise RuntimeError("api broke")

    class FakeClient:
        def __init__(self) -> None:
            self.models = FakeModels()

    monkeypatch.setattr(prompts_mod, "_get_genai_client", lambda: FakeClient())

    out = prompts_mod.generate_prompts_api(tmp_path, style="playful")
    assert set(out.keys()) == {"1_to_2", "2_to_3"}
    for v in out.values():
        assert v == STYLE_PRESETS["playful"]
