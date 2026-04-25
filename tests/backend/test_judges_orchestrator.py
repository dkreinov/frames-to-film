"""Orchestrator tests — JUDGES_ENABLED flag, run.json shape, idempotency.

All judge LLM calls monkeypatched at the orchestrator's import boundary
(`backend.services.judges.score_*`). Tests run offline.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.judges import JudgeScore
from backend.services.judges import orchestrator


# --- is_enabled flag --------------------------------------------------

def test_is_enabled_explicit_on(monkeypatch):
    monkeypatch.setenv("JUDGES_ENABLED", "on")
    assert orchestrator.is_enabled() is True


def test_is_enabled_explicit_off(monkeypatch):
    monkeypatch.setenv("JUDGES_ENABLED", "off")
    monkeypatch.setenv("gemini", "fake-key")
    assert orchestrator.is_enabled() is False


def test_is_enabled_auto_with_gemini_key(monkeypatch):
    monkeypatch.delenv("JUDGES_ENABLED", raising=False)
    monkeypatch.setenv("gemini", "fake")
    assert orchestrator.is_enabled() is True


def test_is_enabled_auto_without_gemini_key(monkeypatch):
    monkeypatch.delenv("JUDGES_ENABLED", raising=False)
    monkeypatch.delenv("gemini", raising=False)
    assert orchestrator.is_enabled() is False


# --- run.json read/write ---------------------------------------------

def test_read_run_json_creates_default_when_missing(tmp_path):
    data = orchestrator.read_run_json(tmp_path)
    assert data["project_id"] == tmp_path.name
    assert data["judges"] == {"prompt": [], "clip": [], "movie": None}
    assert data["cost_usd_total"] == 0.0


def test_write_then_read_roundtrip(tmp_path):
    orig = orchestrator.read_run_json(tmp_path)
    orig["cost_usd_total"] = 1.234
    orchestrator.write_run_json(tmp_path, orig)
    loaded = orchestrator.read_run_json(tmp_path)
    assert loaded["cost_usd_total"] == 1.234


def test_corrupt_run_json_returns_default(tmp_path):
    (tmp_path / "run.json").write_text("not json {", encoding="utf-8")
    data = orchestrator.read_run_json(tmp_path)
    assert data["judges"]["prompt"] == []


# --- post-generate orchestrator -------------------------------------

def _make_project(tmp_path: Path) -> Path:
    """Build a minimal kling_test/ + prompts.json + 2 mp4 stubs."""
    img = tmp_path / "kling_test"
    img.mkdir()
    for n in (1, 2, 3):
        (img / f"{n}.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    video = img / "videos"
    video.mkdir()
    (video / "seg_1_to_2.mp4").write_bytes(b"\x00\x00\x00 ftypmp42")
    (video / "seg_2_to_3.mp4").write_bytes(b"\x00\x00\x00 ftypmp42")
    (tmp_path / "prompts.json").write_text(json.dumps({
        "1_to_2": "Slow dolly in",
        "2_to_3": "Cinematic morph",
    }))
    return tmp_path


def test_post_generate_runs_both_judges_per_pair(tmp_path, monkeypatch):
    project = _make_project(tmp_path)

    fake_prompt = JudgeScore(
        judge="prompt_judge", scores={"prompt_image_alignment": 4.0},
        reasoning="ok", model_used="gemini-2.5-flash-lite", cost_usd=0.0001,
    )
    fake_clip = JudgeScore(
        judge="clip_judge",
        scores={"visual_quality": 4.0, "anatomy_ok": True,
                "style_consistency": 4.0, "prompt_match": 4.0},
        reasoning="solid", model_used="gemini-3-flash-preview", cost_usd=0.0,
    )
    monkeypatch.setattr(orchestrator, "score_prompt", lambda **kw: fake_prompt)
    monkeypatch.setattr(orchestrator, "score_clip", lambda **kw: fake_clip)

    data = orchestrator.run_post_generate_judges(project, gemini_key="fake")
    assert len(data["judges"]["prompt"]) == 2
    assert len(data["judges"]["clip"]) == 2
    assert data["judges"]["prompt"][0]["pair"] == "1_to_2"
    assert data["judges"]["clip"][1]["pair"] == "2_to_3"
    assert data["cost_usd_total"] > 0


def test_post_generate_no_key_writes_neutral_fallbacks(tmp_path):
    project = _make_project(tmp_path)
    data = orchestrator.run_post_generate_judges(project, gemini_key="")
    # Without a key, prompt judges still get logged with neutral 3.0
    # so run.json shape stays consistent for the eval harness.
    assert all(
        e["scores"]["prompt_image_alignment"] == 3.0
        for e in data["judges"]["prompt"]
    )


def test_post_generate_is_idempotent(tmp_path, monkeypatch):
    project = _make_project(tmp_path)
    fake_prompt = JudgeScore(
        judge="prompt_judge", scores={"prompt_image_alignment": 4.0},
        model_used="x", cost_usd=0.0,
    )
    fake_clip = JudgeScore(
        judge="clip_judge",
        scores={"visual_quality": 4.0, "anatomy_ok": True,
                "style_consistency": 4.0, "prompt_match": 4.0},
        model_used="x", cost_usd=0.0,
    )
    monkeypatch.setattr(orchestrator, "score_prompt", lambda **kw: fake_prompt)
    monkeypatch.setattr(orchestrator, "score_clip", lambda **kw: fake_clip)

    orchestrator.run_post_generate_judges(project, gemini_key="k")
    orchestrator.run_post_generate_judges(project, gemini_key="k")
    data = orchestrator.read_run_json(project)
    # Re-running should overwrite, not append, so still 2 (not 4).
    assert len(data["judges"]["prompt"]) == 2
    assert len(data["judges"]["clip"]) == 2


# --- post-stitch orchestrator ----------------------------------------

def test_post_stitch_uses_existing_clip_judges(tmp_path, monkeypatch):
    project = _make_project(tmp_path)
    # Seed clip judges in run.json
    data = orchestrator.read_run_json(project)
    data["judges"]["clip"] = [
        {"pair": "1_to_2", "scores": {"visual_quality": 4.0, "anatomy_ok": True},
         "reasoning": "ok"},
    ]
    orchestrator.write_run_json(project, data)

    fake_movie = JudgeScore(
        judge="movie_judge",
        scores={"story_coherence": 3.5, "character_continuity": 3.5,
                "visual_quality": 3.5, "emotional_arc": 3.5},
        reasoning="works", weakest_seam=1,
        model_used="deepseek-chat", cost_usd=0.0002,
    )
    monkeypatch.setattr(orchestrator, "score_movie", lambda **kw: fake_movie)

    data = orchestrator.run_post_stitch_judge(project, deepseek_key="k")
    assert data["judges"]["movie"]["scores"]["story_coherence"] == 3.5
    assert data["judges"]["movie"]["weakest_seam"] == 1
    assert data["cost_usd_total"] > 0


def test_post_stitch_skips_when_no_clip_judges(tmp_path):
    project = _make_project(tmp_path)
    data = orchestrator.run_post_stitch_judge(project, deepseek_key="k")
    assert "no per-clip judge data" in data["judges"]["movie"]["reasoning"]


def test_post_stitch_no_key_neutral_fallback(tmp_path):
    project = _make_project(tmp_path)
    data = orchestrator.read_run_json(project)
    data["judges"]["clip"] = [{"pair": "1_to_2", "scores": {"visual_quality": 4.0}}]
    orchestrator.write_run_json(project, data)
    data = orchestrator.run_post_stitch_judge(project, deepseek_key="")
    assert "DEEPSEEK_KEY" in data["judges"]["movie"]["reasoning"]
