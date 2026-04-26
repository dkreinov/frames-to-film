"""Integration test for tools/cli/run_prompts.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tmp_project_with_story(tmp_path: Path) -> Path:
    """Project skeleton with extended/ images + metadata/story.json."""
    project = tmp_path / "test_proj"
    (project / "extended").mkdir(parents=True)
    (project / "metadata").mkdir(parents=True)
    # 3 fake jpgs in extended (so 2 pairs)
    for i in range(1, 4):
        (project / "extended" / f"{i}.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    # Story with 2 pair_intents matching
    (project / "metadata" / "story.json").write_text(json.dumps({
        "arc_paragraph": "test arc",
        "pair_intents": [
            {"from": 1, "to": 2, "device": "cross_dissolve",
             "intent": "Slow forward"},
            {"from": 2, "to": 3, "device": "age_match_cut",
             "intent": "Time passes"},
        ],
        "arc_type": "life-montage",
    }))
    return project


def test_run_prompts_mock_mode_writes_prompts_json(tmp_project_with_story):
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "cli" / "run_prompts.py"),
         "--project", str(tmp_project_with_story),
         "--mock"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    prompts_path = tmp_project_with_story / "prompts" / "prompts.json"
    assert prompts_path.is_file()
    data = json.loads(prompts_path.read_text())
    # 2 pairs expected
    assert len(data) == 2
    assert "1_to_2" in data
    assert "2_to_3" in data
    # Each value is a non-empty string
    for k, v in data.items():
        assert isinstance(v, str) and len(v) > 0


def test_run_prompts_fails_without_story(tmp_path):
    """No story.json → exit code 1 with clear error."""
    project = tmp_path / "no_story"
    (project / "extended").mkdir(parents=True)
    (project / "extended" / "1.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    (project / "extended" / "2.jpg").write_bytes(b"\xff\xd8\xff\xe0")

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "cli" / "run_prompts.py"),
         "--project", str(project),
         "--mock"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "story" in result.stderr.lower()
