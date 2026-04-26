"""Integration test for tools/cli/run_story.py.

Mocks story._call_vision so the test runs offline. Verifies the CLI
produces metadata/story.json with the right shape.
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
def tmp_project(tmp_path: Path) -> Path:
    """Create a tmp project skeleton with 3 fake photos in inputs/."""
    project = tmp_path / "test_proj"
    project.mkdir()
    (project / "inputs").mkdir()
    (project / "metadata").mkdir()
    (project / "metadata" / "logs").mkdir()
    # Fake jpgs (header bytes; no real content needed for --mock path)
    for i in range(1, 4):
        (project / "inputs" / f"{i}.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    (project / "metadata" / "project.json").write_text(json.dumps({
        "slug": "test_proj",
        "name": "Test Project",
        "created_at": "2026-04-26",
        "status": "draft",
        "tags": [],
        "source": "test",
    }))
    return project


def test_run_story_mock_mode_writes_story_json(tmp_project):
    """--mock skips LLM; CLI should still write a well-formed story.json."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "cli" / "run_story.py"),
         "--project", str(tmp_project),
         "--arc-type", "life-montage",
         "--subject", "test subject",
         "--tone", "test tone",
         "--mock"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    story_path = tmp_project / "metadata" / "story.json"
    assert story_path.is_file(), "story.json not written"
    data = json.loads(story_path.read_text())
    assert "arc_paragraph" in data
    assert "pair_intents" in data
    # 3 photos = 2 pairs
    assert len(data["pair_intents"]) == 2
    assert data["pair_intents"][0]["from"] == 1
    assert data["pair_intents"][0]["to"] == 2
    assert "device" in data["pair_intents"][0]


def test_run_story_fails_without_inputs(tmp_path):
    """No inputs/ dir → exit code 1 with clear error."""
    project = tmp_path / "empty_proj"
    project.mkdir()
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "cli" / "run_story.py"),
         "--project", str(project),
         "--arc-type", "life-montage",
         "--mock"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0, "should fail without inputs/"
    assert "inputs" in result.stderr.lower() or "inputs" in result.stdout.lower()


def test_run_story_fails_with_too_few_photos(tmp_path):
    """1 photo isn't enough for any pair."""
    project = tmp_path / "tiny_proj"
    project.mkdir()
    (project / "inputs").mkdir()
    (project / "inputs" / "1.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "cli" / "run_story.py"),
         "--project", str(project),
         "--arc-type", "life-montage",
         "--mock"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
