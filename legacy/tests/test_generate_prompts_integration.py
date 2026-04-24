"""Step 7: wire generate_all_videos.run() to prompts.json (TDD red).

When run() is called with a project_dir that contains prompts.json, the
module's PROJECT_PROMPTS global must be populated for the duration of
main() and restored on exit. The lookup precedence seen by main() is:
  PROJECT_PROMPTS > PAIR_PROMPTS > FALLBACK_PROMPT.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _reset_globals():
    """Reset PROJECT_PROMPTS between tests to avoid leakage."""
    import generate_all_videos
    generate_all_videos.PROJECT_PROMPTS = {}
    yield
    generate_all_videos.PROJECT_PROMPTS = {}


def test_run_loads_prompts_json_into_module_global(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import generate_all_videos
    # seed a project-like dir with prompts.json + kling_test/videos/
    (tmp_path / "kling_test").mkdir()
    (tmp_path / "kling_test" / "videos").mkdir()
    prompts = {"1_to_2": "PROJECT-PROMPT-12", "2_to_3": "PROJECT-PROMPT-23"}
    (tmp_path / "prompts.json").write_text(json.dumps(prompts))

    captured: dict = {}

    def capture_main():
        captured["PROJECT_PROMPTS"] = dict(generate_all_videos.PROJECT_PROMPTS)

    monkeypatch.setattr(generate_all_videos, "main", capture_main)

    generate_all_videos.run(
        img_dir=tmp_path / "kling_test",
        video_dir=tmp_path / "kling_test" / "videos",
        project_dir=tmp_path,
    )
    assert captured["PROJECT_PROMPTS"] == prompts


def test_run_restores_project_prompts_on_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import generate_all_videos
    (tmp_path / "kling_test").mkdir()
    (tmp_path / "kling_test" / "videos").mkdir()
    (tmp_path / "prompts.json").write_text(json.dumps({"1_to_2": "X"}))
    monkeypatch.setattr(generate_all_videos, "main", lambda: None)

    generate_all_videos.run(
        img_dir=tmp_path / "kling_test",
        video_dir=tmp_path / "kling_test" / "videos",
        project_dir=tmp_path,
    )
    assert generate_all_videos.PROJECT_PROMPTS == {}  # restored


def test_run_tolerates_missing_prompts_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No prompts.json in project_dir -> PROJECT_PROMPTS stays empty; main() runs normally."""
    import generate_all_videos
    (tmp_path / "kling_test").mkdir()
    (tmp_path / "kling_test" / "videos").mkdir()

    observed = []

    def capture():
        observed.append(dict(generate_all_videos.PROJECT_PROMPTS))

    monkeypatch.setattr(generate_all_videos, "main", capture)
    generate_all_videos.run(
        img_dir=tmp_path / "kling_test",
        video_dir=tmp_path / "kling_test" / "videos",
        project_dir=tmp_path,
    )
    assert observed == [{}]
