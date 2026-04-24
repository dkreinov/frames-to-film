"""Phase 5 Sub-Plan 2 Step 12: real fal.ai Kling O3 smoke test.

Skipped unless the FAL_KEY env var is set. When run, sends ONE real
5-second generation to fal.ai using two fixture photos. Verifies an
mp4 comes back. Costs ~$0.42 on your fal.ai balance.

Run manually:
    FAL_KEY=fal-your-real-key python -m pytest tests/backend/test_kling_fal_real.py -v -s

CI skips this test entirely (no key → pytest skip marker).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.services import kling_fal

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "fake_project"

pytestmark = pytest.mark.skipif(
    not os.getenv("FAL_KEY"),
    reason="FAL_KEY env var not set; skipping real fal.ai smoke test.",
)


def test_one_real_kling_o3_5s_clip(tmp_path):
    """Generate one 5s first-last-frame clip from fixture photos."""
    fal_key = os.environ["FAL_KEY"]
    frame_a = FIXTURE_DIR / "frame_1_gemini.png"
    frame_b = FIXTURE_DIR / "frame_2_gemini.png"
    assert frame_a.is_file(), frame_a
    assert frame_b.is_file(), frame_b

    print(f"\n[fal.ai smoke] starting real generation — this takes 1-3 min and costs ~$0.42")
    mp4_bytes = kling_fal.generate_pair(
        frame_a,
        frame_b,
        prompt="Smooth cinematic transition from the first frame to the second frame.",
        fal_key=fal_key,
        duration=5,
    )

    # mp4 sanity: ftyp atom in first 32 bytes, non-trivial size.
    assert len(mp4_bytes) > 10_000, f"mp4 suspiciously small: {len(mp4_bytes)} bytes"
    assert b"ftyp" in mp4_bytes[:32], "missing mp4 ftyp atom"

    # Write to tmp so the tester can play it back if they want.
    out = tmp_path / "smoke.mp4"
    out.write_bytes(mp4_bytes)
    print(f"[fal.ai smoke] OK — {len(mp4_bytes) / 1024:.1f} KB written to {out}")
