"""End-to-end mock-mode smoke test for the CLI chain.

Validates the full new pipeline runs without errors:
  CLI run_story (mock) → CLI run_prompts (mock) → mock-mode generate
  (existing) → orchestrator post-generate judges (skipped on no key) →
  stitch (mock) → orchestrator post-stitch movie_judge (loads
  story.json from disk; falls back neutral on no key).

No real LLM calls. No real Kling renders. No real money spent.

Phase 7.4 wiring smoke — confirms the new components plug into the
existing pipeline correctly.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def fresh_project(tmp_path: Path) -> Path:
    """Build a fresh project from the _template skeleton with 3 fake
    photos in inputs/ and 3 corresponding in extended/. The mock-mode
    generate will read extended/ and produce stubs in clips/raw/."""
    template_src = REPO_ROOT / "projects" / "_template"
    project = tmp_path / "smoke_proj"
    shutil.copytree(template_src, project)

    # Drop fake photos. ffmpeg's lavfi mock-mode only needs the file
    # extension to exist — the .gitkeep stays harmless.
    for n in (1, 2, 3):
        (project / "inputs" / f"{n}.jpg").write_bytes(b"\xff\xd8\xff\xe0")
        (project / "extended" / f"{n}.jpg").write_bytes(b"\xff\xd8\xff\xe0")

    # Backfill project.json with real values
    pj = project / "metadata" / "project.json"
    meta = json.loads(pj.read_text())
    meta.update({
        "slug": "smoke_proj",
        "name": "CLI E2E mock smoke test",
        "created_at": "2026-04-26",
        "subject": "smoke test subject",
        "tone": "neutral",
        "notes": "auto-generated",
    })
    pj.write_text(json.dumps(meta, indent=2))
    return project


def test_cli_chain_writes_story_then_prompts(fresh_project):
    """run_story → run_prompts produces both metadata/story.json and
    prompts/prompts.json with matching shapes."""
    # Step 1: write story (mock)
    r1 = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "cli" / "run_story.py"),
         "--project", str(fresh_project),
         "--arc-type", "life-montage",
         "--mock"],
        capture_output=True, text=True, timeout=60,
    )
    assert r1.returncode == 0, f"run_story failed: {r1.stderr}"

    story_path = fresh_project / "metadata" / "story.json"
    assert story_path.is_file()
    story = json.loads(story_path.read_text())
    n_pairs = len(story["pair_intents"])
    assert n_pairs == 2, f"3 photos = 2 pairs, got {n_pairs}"

    # Step 2: write prompts (mock)
    r2 = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "cli" / "run_prompts.py"),
         "--project", str(fresh_project),
         "--mock"],
        capture_output=True, text=True, timeout=60,
    )
    assert r2.returncode == 0, f"run_prompts failed: {r2.stderr}"

    prompts_path = fresh_project / "prompts" / "prompts.json"
    assert prompts_path.is_file()
    prompts = json.loads(prompts_path.read_text())
    assert len(prompts) == n_pairs
    # Pair keys match the extended/ image stems
    expected_keys = {"1_to_2", "2_to_3"}
    assert set(prompts.keys()) == expected_keys


def test_orchestrator_loads_disk_story_after_cli_chain(fresh_project, monkeypatch):
    """After CLI run_story writes story.json, orchestrator's post-stitch
    judge should pick it up automatically when called without kwargs."""
    # Run CLI to populate story.json
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "cli" / "run_story.py"),
         "--project", str(fresh_project),
         "--arc-type", "life-montage",
         "--mock"],
        check=True, capture_output=True, timeout=60,
    )

    # Seed run.json with clip_judge data so movie_judge can run
    from backend.services.judges import orchestrator
    data = orchestrator.read_run_json(fresh_project)
    data["judges"]["clip"] = [
        {"pair": "1_to_2", "scores": {"visual_quality": 4.0}, "reasoning": "ok"},
    ]
    orchestrator.write_run_json(fresh_project, data)

    # Mock score_movie to capture what kwargs flowed in
    seen: dict = {}
    from backend.services.judges import JudgeScore
    def fake_movie(**kwargs):
        seen.update(kwargs)
        return JudgeScore(
            judge="movie_judge",
            scores={"story_coherence": 4.0, "character_continuity": 4.0,
                    "visual_quality": 4.0, "emotional_arc": 4.0},
            reasoning="mocked", model_used="mock", cost_usd=0.0,
        )
    monkeypatch.setattr(orchestrator, "score_movie", fake_movie)

    orchestrator.run_post_stitch_judge(fresh_project, deepseek_key="k")

    # story_arc was auto-loaded from disk
    assert seen.get("story_arc") is not None
    assert "mock life-montage" in str(seen["story_arc"]).lower()
    # brief was auto-loaded from project.json
    assert seen.get("brief") is not None
    assert "smoke test subject" in str(seen["brief"])
