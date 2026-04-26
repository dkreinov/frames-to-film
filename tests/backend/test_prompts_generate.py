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
    d = dir_ / "extended"
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
    saved = json.loads((tmp_path / "prompts" / "prompts.json").read_text())
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

    monkeypatch.setattr(prompts_mod, "_get_genai_client", lambda key: FakeClient())

    out = prompts_mod.generate_prompts_api(tmp_path, style="cinematic", key="test-key")
    assert set(out.keys()) == {"1_to_2", "2_to_3", "3_to_4", "4_to_5", "5_to_6"}
    # 5 API calls, each using the flash model
    assert len(calls) == 5
    assert all(c["model"] == "gemini-2.0-flash" for c in calls)
    # generated prompts persisted
    saved = json.loads((tmp_path / "prompts" / "prompts.json").read_text())
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
    (tmp_path / "metadata" / "order.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "metadata" / "order.json").write_text(
        json.dumps({"order": ["3.jpg", "1.jpg", "2.jpg"]})
    )
    assert _pair_keys_for_project(tmp_path) == ["3_to_1", "1_to_2"]


def test_pair_keys_fall_back_when_order_references_missing_files(tmp_path: Path) -> None:
    """If order.json references frames that no longer exist, drop them and
    fall back to numeric sort if nothing valid remains."""
    from backend.services.prompts import _pair_keys_for_project

    _seed_kling(tmp_path, 3)
    (tmp_path / "metadata" / "order.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "metadata" / "order.json").write_text(
        json.dumps({"order": ["ghost.jpg", "also-ghost.jpg"]})
    )
    # All referenced files are missing -> fall back to numeric sort.
    assert _pair_keys_for_project(tmp_path) == ["1_to_2", "2_to_3"]


def test_mock_generator_pairs_follow_order_json(tmp_path: Path) -> None:
    """End-to-end: writing order.json before mock-gen yields prompts.json
    keyed by the reordered pair_keys."""
    _seed_kling(tmp_path, 4)
    (tmp_path / "metadata" / "order.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "metadata" / "order.json").write_text(
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

    monkeypatch.setattr(prompts_mod, "_get_genai_client", lambda key: FakeClient())

    out = prompts_mod.generate_prompts_api(tmp_path, style="playful", key="test-key")
    assert set(out.keys()) == {"1_to_2", "2_to_3"}
    for v in out.values():
        assert v == STYLE_PRESETS["playful"]


# --- Phase 4 sub-plan 6 Step 1: X-Gemini-Key resolver ---

def test_resolve_gemini_key_prefers_header_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.deps import resolve_gemini_key

    monkeypatch.setenv("gemini", "env-key")
    assert resolve_gemini_key("header-key") == "header-key"


def test_resolve_gemini_key_falls_back_to_env_when_header_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.deps import resolve_gemini_key

    monkeypatch.setenv("gemini", "env-key")
    assert resolve_gemini_key(None) == "env-key"
    assert resolve_gemini_key("") == "env-key"
    assert resolve_gemini_key("   ") == "env-key"


def test_resolve_gemini_key_raises_400_when_neither_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException
    from backend.deps import resolve_gemini_key

    monkeypatch.delenv("gemini", raising=False)
    with pytest.raises(HTTPException) as exc:
        resolve_gemini_key(None)
    assert exc.value.status_code == 400
    assert "Gemini API key required" in exc.value.detail


def test_prompts_api_endpoint_surfaces_header_key_to_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full HTTP round-trip: POST /prompts/generate with X-Gemini-Key ->
    the background runner receives the key via the job payload and
    passes it to _get_genai_client."""
    from fastapi.testclient import TestClient
    from backend.deps import get_db_path, get_storage_root
    from backend.main import app
    from backend.services import prompts as prompts_mod

    db = tmp_path / "index.db"
    storage = tmp_path / "projects"
    storage.mkdir()
    app.dependency_overrides[get_db_path] = lambda: db
    app.dependency_overrides[get_storage_root] = lambda: storage

    # Record which key _get_genai_client was called with.
    received_keys: list[str] = []

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeModels:
        def generate_content(self, **_ignored):
            return FakeResponse("generated")

    class FakeClient:
        def __init__(self) -> None:
            self.models = FakeModels()

    def fake_get_client(key: str):
        received_keys.append(key)
        return FakeClient()

    monkeypatch.setattr(prompts_mod, "_get_genai_client", fake_get_client)
    monkeypatch.delenv("gemini", raising=False)  # force header path

    try:
        with TestClient(app) as c:
            pid = c.post("/projects", json={"name": "X"}).json()["project_id"]
            # Seed kling_test frames.
            d = storage / "local" / pid / "extended"
            d.mkdir(parents=True, exist_ok=True)
            from PIL import Image
            for i in range(1, 4):
                Image.new("RGB", (16, 16), (i * 30, 0, 0)).save(d / f"{i}.jpg", "JPEG")

            r = c.post(
                f"/projects/{pid}/prompts/generate",
                json={"mode": "api", "style": "cinematic"},
                headers={"X-Gemini-Key": "header-key-xyz"},
            )
            assert r.status_code == 202, r.text
    finally:
        app.dependency_overrides.clear()

    assert received_keys == ["header-key-xyz"]


def test_prompts_api_endpoint_400_when_api_mode_and_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /prompts/generate with mode=api and no header + no env -> 400."""
    from fastapi.testclient import TestClient
    from backend.deps import get_db_path, get_storage_root
    from backend.main import app

    db = tmp_path / "index.db"
    storage = tmp_path / "projects"
    storage.mkdir()
    app.dependency_overrides[get_db_path] = lambda: db
    app.dependency_overrides[get_storage_root] = lambda: storage
    monkeypatch.delenv("gemini", raising=False)

    try:
        with TestClient(app) as c:
            pid = c.post("/projects", json={"name": "X"}).json()["project_id"]
            r = c.post(
                f"/projects/{pid}/prompts/generate",
                json={"mode": "api", "style": "cinematic"},
            )
            assert r.status_code == 400
            assert "Gemini API key required" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_prompts_mock_mode_does_not_require_gemini_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mock mode must work without a Gemini key — no 400 surfacing."""
    from fastapi.testclient import TestClient
    from backend.deps import get_db_path, get_storage_root
    from backend.main import app

    db = tmp_path / "index.db"
    storage = tmp_path / "projects"
    storage.mkdir()
    app.dependency_overrides[get_db_path] = lambda: db
    app.dependency_overrides[get_storage_root] = lambda: storage
    monkeypatch.delenv("gemini", raising=False)

    try:
        with TestClient(app) as c:
            pid = c.post("/projects", json={"name": "X"}).json()["project_id"]
            d = storage / "local" / pid / "extended"
            d.mkdir(parents=True, exist_ok=True)
            from PIL import Image
            for i in range(1, 4):
                Image.new("RGB", (16, 16), (i * 30, 0, 0)).save(d / f"{i}.jpg", "JPEG")

            r = c.post(
                f"/projects/{pid}/prompts/generate",
                json={"mode": "mock", "style": "cinematic"},
            )
            assert r.status_code == 202, r.text
    finally:
        app.dependency_overrides.clear()
