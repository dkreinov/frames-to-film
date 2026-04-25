"""Phase 7.1 — real-API smoke tests for the three judges.

Skipped unless the relevant keys are set:
- prompt_judge / clip_judge: `gemini` env var
- movie_judge:               `DEEPSEEK_KEY` env var

When run, sends ONE real call per judge against the wet-test cat-astronaut
fixtures. Costs ~$0.001 total (well under the $0.50 benchmark cap).

Run manually:
    python -m pytest tests/backend/test_judges_real.py -v -s

CI skips these (no keys → pytest skip).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.services.judges import score_clip, score_movie, score_prompt

REPO_ROOT = Path(__file__).resolve().parents[2]
WET_TEST_PROJECT = (
    REPO_ROOT / "pipeline_runs" / "local"
    / "3fadfa16c6454ac28f336f612ca58e2b"
)
KLING_DIR = WET_TEST_PROJECT / "kling_test"
VIDEO_DIR = KLING_DIR / "videos"


@pytest.mark.skipif(
    not os.getenv("gemini"),
    reason="gemini env var not set; skipping real prompt_judge smoke.",
)
def test_prompt_judge_real_smoke():
    img_a = KLING_DIR / "1.jpg"
    img_b = KLING_DIR / "2.jpg"
    if not (img_a.exists() and img_b.exists()):
        pytest.skip("wet-test fixtures missing")

    js = score_prompt(
        image_a=img_a, image_b=img_b,
        prompt_text="Slow cinematic dolly in. Maintain lighting.",
        key=os.environ["gemini"],
    )
    score = js.scores["prompt_image_alignment"]
    assert 1.0 <= score <= 5.0, f"score out of range: {score}"
    assert js.cost_usd > 0
    assert js.input_tokens > 0
    print(f"\n[real prompt_judge] score={score} cost=${js.cost_usd:.6f}")


@pytest.mark.skipif(
    not os.getenv("gemini"),
    reason="gemini env var not set; skipping real clip_judge smoke.",
)
def test_clip_judge_real_smoke():
    video = VIDEO_DIR / "seg_1_to_2.mp4"
    if not video.exists():
        pytest.skip("wet-test seg_1_to_2.mp4 missing")

    js = score_clip(
        video_path=video,
        prompt_text="Slow cinematic dolly in",
        key=os.environ["gemini"],
    )
    vq = js.scores["visual_quality"]
    assert 1.0 <= vq <= 5.0, f"visual_quality out of range: {vq}"
    assert isinstance(js.scores["anatomy_ok"], bool)
    print(f"\n[real clip_judge] vq={vq} anatomy={js.scores['anatomy_ok']} "
          f"cost=${js.cost_usd:.6f}")


@pytest.mark.skipif(
    not os.getenv("DEEPSEEK_KEY"),
    reason="DEEPSEEK_KEY env var not set; skipping real movie_judge smoke.",
)
def test_movie_judge_real_smoke():
    clip_judges = [
        {"pair": "1_to_2", "visual_quality": 4.0, "anatomy_ok": True,
         "reasoning": "smooth"},
        {"pair": "2_to_3", "visual_quality": 2.5, "anatomy_ok": False,
         "reasoning": "hand merging with object"},
    ]
    js = score_movie(
        clip_judges=clip_judges,
        story_arc={"arc_paragraph": "Cat explores moon"},
        brief={"subject": "cat astronaut", "tone": "wonder"},
        key=os.environ["DEEPSEEK_KEY"],
    )
    sc = js.scores["story_coherence"]
    assert 1.0 <= sc <= 5.0, f"story_coherence out of range: {sc}"
    assert js.cost_usd > 0
    print(f"\n[real movie_judge] story_coh={sc} weakest_seam={js.weakest_seam} "
          f"cost=${js.cost_usd:.6f}")
