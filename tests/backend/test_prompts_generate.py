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
