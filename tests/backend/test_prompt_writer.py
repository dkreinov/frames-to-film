"""Unit tests for backend.services.prompt_writer.

Phase 7.5 — transition-aware prompt writer. Reads kling_prompt_rules +
device template + arc + image content → produces a Kling-ready prompt
string for one pair.

Red phase: fails with ImportError until Step 8 implements prompt_writer.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.services import prompt_writer
from backend.services.prompt_writer import write_prompt


def _make_image(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_bytes(b"\xff\xd8\xff\xe0")
    return p


def _fake_response(text: str = "Slow dolly forward; the cat steps onto the mushroom field."):
    return text, 800, 25


# --- happy path -------------------------------------------------------

def test_write_prompt_happy_path(monkeypatch, tmp_path):
    img_a = _make_image(tmp_path, "a.jpg")
    img_b = _make_image(tmp_path, "b.jpg")

    monkeypatch.setattr(
        prompt_writer, "_call_vision",
        lambda **kwargs: _fake_response(),
    )

    text = write_prompt(
        image_a=img_a,
        image_b=img_b,
        pair_intent={"from": 1, "to": 2, "device": "cross_dissolve",
                     "intent": "Approach the mushroom field"},
        arc_type="3-act-heroic",
        key="fake-key",
    )
    assert isinstance(text, str)
    assert len(text) > 5
    assert "dolly" in text.lower() or "cat" in text.lower()


def test_write_prompt_passes_device_template_to_rubric(monkeypatch, tmp_path):
    img_a = _make_image(tmp_path, "a.jpg")
    img_b = _make_image(tmp_path, "b.jpg")
    seen: dict = {}

    def fake(**kwargs):
        seen["text"] = kwargs.get("rubric", "")
        return _fake_response()

    monkeypatch.setattr(prompt_writer, "_call_vision", fake)

    write_prompt(
        image_a=img_a, image_b=img_b,
        pair_intent={"from": 1, "to": 2, "device": "age_match_cut",
                     "intent": "Time passes — older self emerges"},
        arc_type="life-montage", key="k",
    )
    rubric = seen.get("text", "")
    # Device template content should appear in the rubric
    assert "age" in rubric.lower() or "match" in rubric.lower(), \
        "rubric should reference the chosen device template"


def test_write_prompt_surfaces_kling_forbidden_phrases(monkeypatch, tmp_path):
    img_a = _make_image(tmp_path, "a.jpg")
    img_b = _make_image(tmp_path, "b.jpg")
    seen: dict = {}

    def fake(**kwargs):
        seen["text"] = kwargs.get("rubric", "")
        return _fake_response()

    monkeypatch.setattr(prompt_writer, "_call_vision", fake)

    write_prompt(
        image_a=img_a, image_b=img_b,
        pair_intent={"from": 1, "to": 2, "device": "cross_dissolve",
                     "intent": "Move forward"},
        arc_type="travel-diary", key="k",
    )
    rubric = seen.get("text", "")
    # Rubric should warn against forbidden phrases (cinematic, 4K, etc.)
    has_forbidden_warning = any(
        f.lower() in rubric.lower()
        for f in ["forbidden", "avoid", "do not use"]
    )
    assert has_forbidden_warning, \
        "rubric should instruct model to avoid kling forbidden phrases"


# --- failure / fallback -----------------------------------------------

def test_write_prompt_falls_back_on_call_error(monkeypatch, tmp_path):
    img_a = _make_image(tmp_path, "a.jpg")
    img_b = _make_image(tmp_path, "b.jpg")

    def boom(**kwargs):
        raise RuntimeError("network down")
    monkeypatch.setattr(prompt_writer, "_call_vision", boom)

    text = write_prompt(
        image_a=img_a, image_b=img_b,
        pair_intent={"from": 1, "to": 2, "device": "cross_dissolve",
                     "intent": "Move forward"},
        arc_type="3-act-heroic", key="k",
    )
    # Fallback prompt is non-empty so the pipeline always has SOMETHING
    # to feed Kling, even if the LLM call broke.
    assert isinstance(text, str)
    assert len(text) >= 10


def test_write_prompt_unknown_device_raises(tmp_path):
    img_a = _make_image(tmp_path, "a.jpg")
    img_b = _make_image(tmp_path, "b.jpg")
    with pytest.raises((KeyError, ValueError)):
        write_prompt(
            image_a=img_a, image_b=img_b,
            pair_intent={"from": 1, "to": 2,
                         "device": "totally_invalid_device_id_xyz",
                         "intent": "x"},
            arc_type="3-act-heroic", key="k",
        )


# --- vendor dispatch -------------------------------------------------

def test_prompt_writer_vendor_dispatch():
    assert prompt_writer._vendor_for_model("qwen3-vl-plus") == "qwen"
    assert prompt_writer._vendor_for_model("qwen-vl-plus") == "qwen"
    assert prompt_writer._vendor_for_model("gemini-2.5-flash") == "gemini"
    assert prompt_writer._vendor_for_model("moonshot-v1-128k-vision-preview") == "moonshot"
