"""Tests for backend.services.stitch_xfade filter-graph builder.

All tests are pure-function (no I/O, no ffmpeg binary).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.stitch_xfade import build_xfade_filter_graph

# Minimal device catalog used across tests.
# Mirrors shape of data/cinematic_devices.yaml entries.
DEVICES = {
    "cross_dissolve": {
        "id": "cross_dissolve",
        "ffmpeg_xfade": "fade",
        "xfade_duration_s": 1.0,
    },
    "age_match_cut": {
        "id": "age_match_cut",
        "ffmpeg_xfade": "fade",
        "xfade_duration_s": 1.0,
    },
    "whip_pan": {
        "id": "whip_pan",
        "ffmpeg_xfade": "wipeleft",
        "xfade_duration_s": 0.2,
    },
    "match_cut_action": {
        "id": "match_cut_action",
        "ffmpeg_xfade": "",
        "xfade_duration_s": 0.0,
    },
    "smash_cut": {
        "id": "smash_cut",
        "ffmpeg_xfade": "",
        "xfade_duration_s": 0.0,
    },
    "iris_in": {
        "id": "iris_in",
        "ffmpeg_xfade": "circleopen",
        "xfade_duration_s": 0.8,
    },
}

SEG_A = Path("seg_1_to_2.mp4")
SEG_B = Path("seg_2_to_3.mp4")
SEG_C = Path("seg_3_to_4.mp4")


def _make_segs(*device_ids: str, dur: float = 5.0) -> list[dict]:
    """Build N+1 segments for N transitions (device_ids)."""
    n = len(device_ids) + 1
    paths = [Path(f"seg_{i}_to_{i+1}.mp4") for i in range(1, n + 1)]
    segs = [{"path": paths[0], "duration_s": dur, "device_id": None}]
    for i, dev in enumerate(device_ids):
        segs.append({"path": paths[i + 1], "duration_s": dur, "device_id": dev})
    return segs


def test_two_segments_with_fade_xfade():
    """2 segs × 5s + cross_dissolve (fade, 1.0s) → xfade filter, offset=4, total=9s."""
    segs = _make_segs("cross_dissolve", dur=5.0)
    fc, label, total = build_xfade_filter_graph(segments=segs, devices=DEVICES)

    assert "xfade=transition=fade" in fc
    assert "duration=1" in fc or "duration=1.0" in fc
    # offset = first_clip_duration - xfade_duration = 5.0 - 1.0 = 4.0
    assert "offset=4" in fc
    assert label == "[vout]"
    assert abs(total - 9.0) < 0.01


def test_three_segments_mixed_xfade_and_hardcut():
    """3 segs, transitions: age_match_cut (fade,1.0s) then match_cut_action (hard-cut).
    Expected total = 5 + 5 + 5 - 1 = 14s (only one overlap).
    """
    segs = _make_segs("age_match_cut", "match_cut_action", dur=5.0)
    fc, label, total = build_xfade_filter_graph(segments=segs, devices=DEVICES)

    # First transition is an xfade
    assert "xfade=transition=fade" in fc
    # Second transition is a hard cut → concat filter used, no second xfade
    assert fc.count("xfade") == 1
    assert "concat" in fc
    assert label == "[vout]"
    assert abs(total - 14.0) < 0.01


def test_unknown_device_falls_back_to_default():
    """Unknown device id → use default_xfade_flag (fade) + default_xfade_duration_s (0.5)."""
    segs = _make_segs("made_up_device", dur=5.0)
    fc, label, total = build_xfade_filter_graph(
        segments=segs,
        devices=DEVICES,
        default_xfade_flag="fade",
        default_xfade_duration_s=0.5,
    )
    assert "xfade=transition=fade" in fc
    assert "duration=0.5" in fc
    # offset = 5.0 - 0.5 = 4.5
    assert "offset=4.5" in fc
    assert abs(total - 9.5) < 0.01


def test_single_segment_returns_passthrough():
    """1 segment, 0 transitions → passthrough; total = clip duration."""
    segs = [{"path": SEG_A, "duration_s": 7.0, "device_id": None}]
    fc, label, total = build_xfade_filter_graph(segments=segs, devices=DEVICES)

    # No xfade, no concat needed — passthrough
    assert "[0:v]" in fc
    assert label == "[vout]"
    assert abs(total - 7.0) < 0.01
