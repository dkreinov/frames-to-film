"""Unit tests for the three judges + JudgeScore envelope.

LLM calls are monkeypatched at module level so tests run offline without
keys. One real-API path lives in `test_judges_real.py` (slow_real mark).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.judges import JudgeScore, score_clip, score_movie, score_prompt
from backend.services.judges import clip_judge, movie_judge, prompt_judge
from backend.services.judges.base import estimate_cost


# --- JudgeScore envelope ---------------------------------------------

def test_judge_score_basic_construction():
    js = JudgeScore(
        judge="prompt_judge",
        scores={"prompt_image_alignment": 4.2},
        model_used="gemini-2.5-flash-lite",
    )
    assert js.judge == "prompt_judge"
    assert js.version == "v1"
    assert js.scores["prompt_image_alignment"] == 4.2
    assert js.cost_usd == 0.0


def test_judge_score_is_failing_below_threshold():
    js = JudgeScore(
        judge="clip_judge",
        scores={"visual_quality": 1.5, "anatomy_ok": True},
        model_used="x",
    )
    assert js.is_failing(2.0) is True


def test_judge_score_is_failing_above_threshold():
    js = JudgeScore(
        judge="clip_judge",
        scores={"visual_quality": 4.0, "anatomy_ok": True},
        model_used="x",
    )
    assert js.is_failing(2.0) is False


def test_estimate_cost_known_model():
    # 1k input tokens at $0.10/M = $0.0001; 100 output at $0.40/M = $0.00004
    cost = estimate_cost("gemini-2.5-flash-lite", 1000, 100)
    assert abs(cost - (0.0001 + 0.00004)) < 1e-9


def test_estimate_cost_unknown_model_returns_zero():
    assert estimate_cost("not-a-model", 5000, 500) == 0.0


# --- prompt_judge -----------------------------------------------------

def test_prompt_judge_happy_path(monkeypatch, tmp_path):
    img_a = tmp_path / "a.jpg"
    img_b = tmp_path / "b.jpg"
    img_a.write_bytes(b"\xff\xd8\xff\xe0")
    img_b.write_bytes(b"\xff\xd8\xff\xe0")

    fake_response = (
        '```json\n{"score": 4.5, "reasoning": "well grounded"}\n```',
        850,  # input tokens
        25,   # output tokens
    )
    monkeypatch.setattr(prompt_judge, "_call_vision",
                        lambda **kwargs: fake_response)

    js = score_prompt(image_a=img_a, image_b=img_b,
                      prompt_text="Slow dolly", key="fake-key")
    assert js.judge == "prompt_judge"
    assert js.scores["prompt_image_alignment"] == 4.5
    assert js.reasoning == "well grounded"
    assert js.input_tokens == 850
    assert js.output_tokens == 25
    # Default model is qwen3-vl-plus (Phase 7.1.1 v2 winner)
    assert js.model_used == prompt_judge.DEFAULT_MODEL == "qwen3-vl-plus"


def test_prompt_judge_handles_unfenced_json(monkeypatch, tmp_path):
    img_a = tmp_path / "a.jpg"
    img_b = tmp_path / "b.jpg"
    img_a.write_bytes(b"\xff\xd8\xff\xe0")
    img_b.write_bytes(b"\xff\xd8\xff\xe0")

    monkeypatch.setattr(
        prompt_judge, "_call_vision",
        lambda **kwargs: ('{"score": 2.0, "reasoning": "vague"}', 500, 10),
    )
    js = score_prompt(image_a=img_a, image_b=img_b,
                      prompt_text="x", key="k")
    assert js.scores["prompt_image_alignment"] == 2.0


def test_prompt_judge_falls_back_on_call_error(monkeypatch, tmp_path):
    img_a = tmp_path / "a.jpg"
    img_b = tmp_path / "b.jpg"
    img_a.write_bytes(b"\xff\xd8\xff\xe0")
    img_b.write_bytes(b"\xff\xd8\xff\xe0")

    def boom(**kwargs):
        raise RuntimeError("network down")
    monkeypatch.setattr(prompt_judge, "_call_vision", boom)

    js = score_prompt(image_a=img_a, image_b=img_b,
                      prompt_text="x", key="k")
    # Neutral fallback is the contract: pipeline shouldn't crash.
    assert js.scores["prompt_image_alignment"] == 3.0
    assert "judge error" in js.reasoning


def test_prompt_judge_vendor_dispatch():
    """Vendor selection by model prefix."""
    assert prompt_judge._vendor_for_model("qwen-vl-plus") == "qwen"
    assert prompt_judge._vendor_for_model("qwen3-vl-plus") == "qwen"
    assert prompt_judge._vendor_for_model("gemini-2.5-flash") == "gemini"
    assert prompt_judge._vendor_for_model("moonshot-v1-128k-vision-preview") == "moonshot"


# --- clip_judge -------------------------------------------------------

def test_clip_judge_happy_path(monkeypatch, tmp_path):
    """v2 source-aware: caller passes source_start + source_end + video."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake mp4")
    src_a = tmp_path / "src_a.jpg"
    src_b = tmp_path / "src_b.jpg"
    src_a.write_bytes(b"\xff\xd8\xff\xe0")
    src_b.write_bytes(b"\xff\xd8\xff\xe0")

    # Bypass ffmpeg by monkeypatching frame extraction.
    fake_frames = [tmp_path / f"f{i}.jpg" for i in range(3)]
    for f in fake_frames:
        f.write_bytes(b"\xff\xd8\xff\xe0")
    monkeypatch.setattr(clip_judge, "extract_frames_at_timestamps",
                        lambda *a, **kw: fake_frames)

    monkeypatch.setattr(
        clip_judge, "_call_vision",
        lambda **kwargs: (
            '{"main_character_drift": 4.5, "text_artifacts": 5, '
            '"limb_anatomy": 4, "unnatural_faces": 5, "glitches": 3, '
            '"content_hallucination": 5, "specific_issues": "minor blur"}',
            1200, 35,
        ),
    )

    js = score_clip(
        video_path=video,
        source_start_path=src_a, source_end_path=src_b,
        key="k",
    )
    assert js.judge == "clip_judge"
    assert js.scores["main_character_drift"] == 4.5
    assert js.scores["content_hallucination"] == 5.0
    assert js.scores["glitches"] == 3.0
    assert js.reasoning == "minor blur"
    assert js.input_tokens == 1200
    assert js.model_used == "qwen3-vl-plus"


def test_clip_judge_flags_anatomy_and_text(monkeypatch, tmp_path):
    """v2 catches limb + text artifacts in same response."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    src_a = tmp_path / "src_a.jpg"; src_a.write_bytes(b"\xff\xd8\xff\xe0")
    src_b = tmp_path / "src_b.jpg"; src_b.write_bytes(b"\xff\xd8\xff\xe0")
    fake_frames = [tmp_path / f"f{i}.jpg" for i in range(3)]
    for f in fake_frames:
        f.write_bytes(b"\xff\xd8\xff\xe0")
    monkeypatch.setattr(clip_judge, "extract_frames_at_timestamps",
                        lambda *a, **kw: fake_frames)
    monkeypatch.setattr(
        clip_judge, "_call_vision",
        lambda **kwargs: (
            '{"main_character_drift": 3, "text_artifacts": 1, '
            '"limb_anatomy": 2, "unnatural_faces": 3, "glitches": 3, '
            '"content_hallucination": 4, "specific_issues": "Hebrew text garbled, missing arm"}',
            500, 20,
        ),
    )
    js = score_clip(
        video_path=video,
        source_start_path=src_a, source_end_path=src_b,
        key="k",
    )
    assert js.scores["text_artifacts"] == 1.0
    assert js.scores["limb_anatomy"] == 2.0
    assert "Hebrew" in js.reasoning


def test_clip_judge_falls_back_on_ffmpeg_error(monkeypatch, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    src_a = tmp_path / "src_a.jpg"; src_a.write_bytes(b"\xff\xd8\xff\xe0")
    src_b = tmp_path / "src_b.jpg"; src_b.write_bytes(b"\xff\xd8\xff\xe0")

    def boom(*a, **kw):
        raise RuntimeError("ffmpeg failed")
    monkeypatch.setattr(clip_judge, "extract_frames_at_timestamps", boom)

    js = score_clip(
        video_path=video,
        source_start_path=src_a, source_end_path=src_b,
        key="k",
    )
    # Neutral fallback across all 6 dimensions
    assert js.scores["main_character_drift"] == 3.0
    assert js.scores["content_hallucination"] == 3.0
    assert "frame extraction failed" in js.reasoning


def test_clip_judge_vendor_dispatch():
    """Vendor selection by model prefix."""
    assert clip_judge._vendor_for_model("qwen-vl-plus") == "qwen"
    assert clip_judge._vendor_for_model("qwen3-vl-plus") == "qwen"
    assert clip_judge._vendor_for_model("gemini-3-flash-preview") == "gemini"
    assert clip_judge._vendor_for_model("moonshot-v1-128k-vision-preview") == "moonshot"


# --- movie_judge ------------------------------------------------------

def test_movie_judge_happy_path(monkeypatch):
    monkeypatch.setattr(
        movie_judge, "_call_deepseek",
        lambda **kwargs: (
            '{"story_coherence": 4.0, "character_continuity": 3.5, '
            '"visual_quality": 4.2, "emotional_arc": 3.8, '
            '"weakest_seam": 3, "reasoning": "middle pair has anatomy issue"}',
            900, 60,
        ),
    )

    clip_judges = [
        {"pair": "1_to_2", "visual_quality": 4.0, "anatomy_ok": True},
        {"pair": "2_to_3", "visual_quality": 4.5, "anatomy_ok": True},
        {"pair": "3_to_4", "visual_quality": 2.0, "anatomy_ok": False},
    ]
    js = score_movie(clip_judges=clip_judges, key="k")
    assert js.judge == "movie_judge"
    assert js.scores["story_coherence"] == 4.0
    assert js.weakest_seam == 3
    assert js.input_tokens == 900


def test_movie_judge_no_key_returns_neutral():
    # Pass api_key="" explicitly to bypass env fallback
    js = score_movie(clip_judges=[{"x": 1}], key="")
    assert js.scores["story_coherence"] == 3.0
    assert "DEEPSEEK_KEY" in js.reasoning


def test_movie_judge_falls_back_on_call_error(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("deepseek 500")
    monkeypatch.setattr(movie_judge, "_call_deepseek", boom)

    js = score_movie(clip_judges=[{"x": 1}], key="k")
    assert js.scores["story_coherence"] == 3.0
    assert "judge error" in js.reasoning


def test_movie_judge_includes_story_arc_in_user_message(monkeypatch):
    """Phase 7.4: movie_judge accepts optional story_arc kwarg and
    surfaces it to the LLM. Verifies the kwarg flows through
    _build_user_message into the LLM call."""
    seen: dict = {}

    def fake(**kwargs):
        seen["msg"] = kwargs.get("user_message", "")
        return ('{"story_coherence": 4.0, "character_continuity": 4.0, '
                '"visual_quality": 4.0, "emotional_arc": 4.0, '
                '"weakest_seam": null, "reasoning": "ok"}', 100, 30)
    monkeypatch.setattr(movie_judge, "_call_deepseek", fake)

    story_arc = {
        "arc_paragraph": "Sarah's life from age 5 to 50",
        "pair_intents": [{"from": 1, "to": 2, "device": "age_match_cut",
                          "intent": "Age progression"}],
    }
    score_movie(
        clip_judges=[{"x": 1}],
        story_arc=story_arc,
        key="k",
    )
    msg = seen.get("msg", "")
    assert "STORY ARC" in msg, "story_arc should appear in user message"
    assert "Sarah" in msg, "story_arc content should be serialized"


def test_movie_judge_includes_brief_in_user_message(monkeypatch):
    """Phase 7.4: movie_judge accepts optional brief kwarg."""
    seen: dict = {}

    def fake(**kwargs):
        seen["msg"] = kwargs.get("user_message", "")
        return ('{"story_coherence": 4.0, "character_continuity": 4.0, '
                '"visual_quality": 4.0, "emotional_arc": 4.0, '
                '"weakest_seam": null, "reasoning": "ok"}', 100, 30)
    monkeypatch.setattr(movie_judge, "_call_deepseek", fake)

    brief = {"subject": "Sarah's life", "tone": "nostalgic", "notes": ""}
    score_movie(
        clip_judges=[{"x": 1}],
        brief=brief,
        key="k",
    )
    msg = seen.get("msg", "")
    assert "OPERATOR BRIEF" in msg
    assert "nostalgic" in msg


def test_movie_judge_invalid_weakest_seam(monkeypatch):
    """If the model returns a non-numeric weakest_seam, swallow it."""
    monkeypatch.setattr(
        movie_judge, "_call_deepseek",
        lambda **kwargs: (
            '{"story_coherence": 3.5, "character_continuity": 3.5, '
            '"visual_quality": 3.5, "emotional_arc": 3.5, '
            '"weakest_seam": "not-a-number", "reasoning": ""}',
            100, 10,
        ),
    )
    js = score_movie(clip_judges=[{"x": 1}], key="k")
    assert js.weakest_seam is None
