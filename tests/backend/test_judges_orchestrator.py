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
    (tmp_path / "metadata" / "run.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "metadata" / "run.json").write_text("not json {", encoding="utf-8")
    data = orchestrator.read_run_json(tmp_path)
    assert data["judges"]["prompt"] == []


# --- post-generate orchestrator -------------------------------------

def _make_project(tmp_path: Path) -> Path:
    """Build a minimal extended/ + prompts/prompts.json + 2 mp4 stubs in clips/raw/."""
    img = tmp_path / "extended"
    img.mkdir()
    for n in (1, 2, 3):
        (img / f"{n}.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    video = tmp_path / "clips" / "raw"
    video.mkdir(parents=True)
    (video / "seg_1_to_2.mp4").write_bytes(b"\x00\x00\x00 ftypmp42")
    (video / "seg_2_to_3.mp4").write_bytes(b"\x00\x00\x00 ftypmp42")
    (tmp_path / "prompts" / "prompts.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "prompts" / "prompts.json").write_text(json.dumps({
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
        scores={"main_character_drift": 4.0, "text_artifacts": 5.0,
                "limb_anatomy": 4.0, "unnatural_faces": 5.0,
                "glitches": 4.0, "content_hallucination": 5.0},
        reasoning="solid", model_used="qwen3-vl-plus", cost_usd=0.0,
    )
    monkeypatch.setattr(orchestrator, "score_prompt", lambda **kw: fake_prompt)
    monkeypatch.setattr(orchestrator, "score_clip", lambda **kw: fake_clip)

    data = orchestrator.run_post_generate_judges(project, judge_key="fake")
    assert len(data["judges"]["prompt"]) == 2
    assert len(data["judges"]["clip"]) == 2
    assert data["judges"]["prompt"][0]["pair"] == "1_to_2"
    assert data["judges"]["clip"][1]["pair"] == "2_to_3"
    assert data["cost_usd_total"] > 0


def test_post_generate_no_key_writes_neutral_fallbacks(tmp_path):
    project = _make_project(tmp_path)
    data = orchestrator.run_post_generate_judges(project, judge_key="")
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
        scores={"main_character_drift": 4.0, "text_artifacts": 5.0,
                "limb_anatomy": 4.0, "unnatural_faces": 5.0,
                "glitches": 4.0, "content_hallucination": 5.0},
        model_used="x", cost_usd=0.0,
    )
    monkeypatch.setattr(orchestrator, "score_prompt", lambda **kw: fake_prompt)
    monkeypatch.setattr(orchestrator, "score_clip", lambda **kw: fake_clip)

    orchestrator.run_post_generate_judges(project, judge_key="k")
    orchestrator.run_post_generate_judges(project, judge_key="k")
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


def test_post_stitch_loads_story_arc_from_disk_when_kwarg_absent(tmp_path, monkeypatch):
    """Phase 7.4 wiring: when run_post_stitch_judge is called without an
    explicit story_arc kwarg, it should load metadata/story.json if
    present and forward it to score_movie."""
    project = _make_project(tmp_path)
    data = orchestrator.read_run_json(project)
    data["judges"]["clip"] = [
        {"pair": "1_to_2", "scores": {"visual_quality": 4.0, "anatomy_ok": True},
         "reasoning": "ok"},
    ]
    orchestrator.write_run_json(project, data)
    # Seed story.json with a sentinel arc_paragraph
    from backend.services.project_schema import METADATA_DIRNAME
    story_path = project / METADATA_DIRNAME / "story.json"
    story_path.parent.mkdir(parents=True, exist_ok=True)
    story_path.write_text(json.dumps({
        "arc_paragraph": "SENTINEL_ARC_TEXT_FROM_DISK",
        "pair_intents": [{"from": 1, "to": 2, "device": "fade", "intent": "x"}],
        "arc_type": "life-montage",
    }))

    seen: dict = {}
    def fake_score_movie(**kwargs):
        seen["story_arc"] = kwargs.get("story_arc")
        return JudgeScore(
            judge="movie_judge",
            scores={"story_coherence": 4.0, "character_continuity": 4.0,
                    "visual_quality": 4.0, "emotional_arc": 4.0},
            reasoning="ok", model_used="x", cost_usd=0.0,
        )
    monkeypatch.setattr(orchestrator, "score_movie", fake_score_movie)

    orchestrator.run_post_stitch_judge(project, deepseek_key="k")

    assert seen.get("story_arc") is not None, \
        "story_arc should be auto-loaded from metadata/story.json"
    assert "SENTINEL_ARC_TEXT_FROM_DISK" in str(seen["story_arc"])


def test_post_stitch_loads_brief_from_project_json_when_kwarg_absent(tmp_path, monkeypatch):
    """Phase 7.4: when brief kwarg absent, orchestrator pulls subject/tone/notes
    from metadata/project.json if present."""
    project = _make_project(tmp_path)
    data = orchestrator.read_run_json(project)
    data["judges"]["clip"] = [
        {"pair": "1_to_2", "scores": {"visual_quality": 4.0}, "reasoning": ""},
    ]
    orchestrator.write_run_json(project, data)
    from backend.services.project_schema import METADATA_DIRNAME
    pj_path = project / METADATA_DIRNAME / "project.json"
    pj_path.parent.mkdir(parents=True, exist_ok=True)
    pj_path.write_text(json.dumps({
        "slug": "test", "name": "Test", "created_at": "2026-04-26",
        "subject": "SENTINEL_SUBJECT_FROM_DISK",
        "tone": "nostalgic_sentinel",
        "notes": "extra notes",
    }))

    seen: dict = {}
    def fake_score_movie(**kwargs):
        seen["brief"] = kwargs.get("brief")
        return JudgeScore(
            judge="movie_judge",
            scores={"story_coherence": 4.0, "character_continuity": 4.0,
                    "visual_quality": 4.0, "emotional_arc": 4.0},
            reasoning="ok", model_used="x", cost_usd=0.0,
        )
    monkeypatch.setattr(orchestrator, "score_movie", fake_score_movie)

    orchestrator.run_post_stitch_judge(project, deepseek_key="k")

    assert seen.get("brief") is not None, \
        "brief should be auto-loaded from metadata/project.json"
    assert "SENTINEL_SUBJECT_FROM_DISK" in str(seen["brief"])


# --- order.json loop pair support ------------------------------------

def test_discover_pairs_respects_order_json_loop(tmp_path):
    """_discover_pairs must include the loop pair (25→1) when order.json
    specifies a repeated first filename at the end."""
    from backend.services.project_schema import EXTENDED_DIRNAME, METADATA_DIRNAME
    from backend.services.prompts import ORDER_FILENAME

    project = tmp_path / "proj"
    ext = project / EXTENDED_DIRNAME
    ext.mkdir(parents=True)
    meta = project / METADATA_DIRNAME
    meta.mkdir(parents=True)

    # Create 6 numbered photos in extended/
    for n in (1, 4, 13, 18, 24, 25):
        (ext / f"{n}.jpg").write_bytes(b"\xff\xd8\xff\xe0")

    # order.json specifying loop: 1→4→13→18→24→25→1
    (meta / ORDER_FILENAME).write_text(json.dumps({
        "order": ["1.jpg", "4.jpg", "13.jpg", "18.jpg", "24.jpg", "25.jpg", "1.jpg"]
    }))

    pairs = orchestrator._discover_pairs(project)
    pair_keys = [pk for pk, _, _ in pairs]

    assert len(pairs) == 6, f"expected 6 pairs (incl. loop), got {len(pairs)}: {pair_keys}"
    assert "25_to_1" in pair_keys, f"loop pair 25_to_1 missing from {pair_keys}"
    assert pair_keys[0] == "1_to_4"
    assert pair_keys[-1] == "25_to_1"
