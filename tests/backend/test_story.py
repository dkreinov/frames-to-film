"""Unit tests for backend.services.story (story-writer service).

Phase 7.4 backend prep, Stream A. Tests run offline by monkeypatching
the LLM call at the module's import boundary (`_call_vision`).

Red phase: these tests fail with ImportError until story.py exists
(Step 6 makes them green).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.judges import JudgeScore  # noqa: F401  (sanity import)


# --- service module imports (red phase fails here until Step 6) -------

from backend.services import story
from backend.services.story import StoryDoc, write_story


def _make_image_paths(tmp_path: Path, n: int = 3) -> list[Path]:
    """Tiny valid-jpeg-header bytes so PIL/SDK can open without crashing."""
    paths: list[Path] = []
    for i in range(1, n + 1):
        p = tmp_path / f"{i}.jpg"
        p.write_bytes(b"\xff\xd8\xff\xe0")
        paths.append(p)
    return paths


def _fake_llm_response_text(n_pairs: int) -> str:
    pair_intents = ", ".join(
        f'{{"from": {i}, "to": {i + 1}, "device": "cross_dissolve", '
        f'"intent": "Slow dolly forward."}}'
        for i in range(1, n_pairs + 1)
    )
    return (
        '{"arc_paragraph": "A test arc paragraph spanning three beats.", '
        f'"pair_intents": [{pair_intents}]}}'
    )


# --- StoryDoc shape ---------------------------------------------------

def test_story_doc_minimum_construction():
    doc = StoryDoc(
        arc_paragraph="x",
        pair_intents=[{"from": 1, "to": 2, "device": "cross_dissolve",
                       "intent": "y"}],
        model_used="qwen3-vl-plus",
    )
    assert doc.arc_paragraph == "x"
    assert len(doc.pair_intents) == 1


# --- write_story happy path ------------------------------------------

def test_write_story_happy_path(monkeypatch, tmp_path):
    images = _make_image_paths(tmp_path, n=3)
    monkeypatch.setattr(
        story, "_call_vision",
        lambda **kwargs: (_fake_llm_response_text(2), 1500, 200),
    )

    doc = write_story(
        image_paths=images,
        brief={"subject": "test subject", "tone": "test tone", "notes": ""},
        arc_type="life-montage",
        key="fake-key",
    )
    assert isinstance(doc, StoryDoc)
    assert "test arc paragraph" in doc.arc_paragraph
    assert len(doc.pair_intents) == 2
    assert doc.pair_intents[0]["device"] == "cross_dissolve"
    assert doc.input_tokens == 1500
    assert doc.output_tokens == 200
    assert doc.model_used == story.DEFAULT_MODEL == "qwen3-vl-plus"
    assert doc.cost_usd > 0


def test_write_story_loads_arc_template_into_rubric(monkeypatch, tmp_path):
    """Verify story.py loads data/story_arcs/{arc_type}.yaml content
    into the LLM call (so the model sees the arc-specific guidance)."""
    images = _make_image_paths(tmp_path, n=2)
    seen_rubric: dict = {}

    def fake_call(**kwargs):
        seen_rubric["text"] = kwargs.get("rubric", "")
        return _fake_llm_response_text(1), 100, 30

    monkeypatch.setattr(story, "_call_vision", fake_call)

    write_story(
        image_paths=images,
        brief={"subject": "x", "tone": "y", "notes": ""},
        arc_type="life-montage",
        key="k",
    )
    rubric = seen_rubric.get("text", "")
    # Arc-specific keywords from data/story_arcs/life_montage.yaml
    # should appear in the rubric we send to the LLM.
    assert "life" in rubric.lower() or "montage" in rubric.lower(), \
        "rubric should reference the chosen arc type"


def test_write_story_passes_kling_rules_to_rubric(monkeypatch, tmp_path):
    """Verify kling_prompt_rules.yaml constraints flow into the rubric."""
    images = _make_image_paths(tmp_path, n=2)
    seen: dict = {}

    def fake_call(**kwargs):
        seen["text"] = kwargs.get("rubric", "")
        return _fake_llm_response_text(1), 100, 30

    monkeypatch.setattr(story, "_call_vision", fake_call)

    write_story(
        image_paths=images,
        brief={"subject": "x", "tone": "y", "notes": ""},
        arc_type="3-act-heroic",
        key="k",
    )
    rubric = seen.get("text", "")
    # Kling-rules-driven constraints we want surfaced
    assert "motion" in rubric.lower(), \
        "rubric should mention motion (kling i2v core rule)"


# --- failure / fallback paths ----------------------------------------

def test_write_story_falls_back_on_call_error(monkeypatch, tmp_path):
    images = _make_image_paths(tmp_path, n=2)

    def boom(**kwargs):
        raise RuntimeError("network down")
    monkeypatch.setattr(story, "_call_vision", boom)

    doc = write_story(
        image_paths=images,
        brief={"subject": "x", "tone": "y", "notes": ""},
        arc_type="life-montage",
        key="k",
    )
    # Pipeline must keep going even if the LLM call fails.
    assert isinstance(doc, StoryDoc)
    assert "judge error" in doc.reasoning.lower() or \
           "story error" in doc.reasoning.lower() or \
           "fallback" in doc.reasoning.lower()


def test_write_story_unknown_arc_type_raises(tmp_path):
    images = _make_image_paths(tmp_path, n=2)
    with pytest.raises((FileNotFoundError, ValueError, KeyError)):
        write_story(
            image_paths=images,
            brief={"subject": "x", "tone": "y", "notes": ""},
            arc_type="not-a-real-arc",
            key="k",
        )


# --- rubric motion-only enforcement ----------------------------------

def test_rubric_forbids_content_nouns(monkeypatch, tmp_path):
    """_build_rubric must explicitly prohibit object/prop/person/place nouns
    in pair_intents — not just say 'only motion'. The LLM needs strong
    negative constraints to avoid content hallucination in prompts."""
    images = _make_image_paths(tmp_path, n=3)
    seen: dict = {}

    def fake_call(**kwargs):
        seen["rubric"] = kwargs.get("rubric", "")
        return _fake_llm_response_text(2), 100, 30

    monkeypatch.setattr(story, "_call_vision", fake_call)
    write_story(
        image_paths=images,
        brief={"subject": "x", "tone": "y", "notes": ""},
        arc_type="life-montage",
        key="k",
    )
    rubric = seen.get("rubric", "")
    # Must explicitly prohibit content nouns — "only describe motion" is not enough
    assert any(phrase in rubric.lower() for phrase in [
        "never include", "do not include", "no objects", "no nouns",
        "never mention", "prohibited", "forbidden words",
    ]), f"rubric must explicitly prohibit content nouns; got:\n{rubric[-600:]}"
    # Must specify what a good intent looks like — format guidance
    assert any(phrase in rubric.lower() for phrase in [
        "camera verb", "camera movement", "bad:", "good:", "example:",
        "format:", "must contain", "only camera",
    ]), f"rubric must include format guidance or contrast example; got:\n{rubric[-600:]}"


# --- vendor dispatch -------------------------------------------------

def test_story_vendor_dispatch():
    """Vendor selection by model prefix mirrors clip_judge."""
    assert story._vendor_for_model("qwen3-vl-plus") == "qwen"
    assert story._vendor_for_model("qwen-vl-plus") == "qwen"
    assert story._vendor_for_model("gemini-2.5-flash") == "gemini"
    assert story._vendor_for_model("moonshot-v1-128k-vision-preview") == "moonshot"
