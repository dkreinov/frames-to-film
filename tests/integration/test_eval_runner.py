"""Integration tests for tools/eval_runner.py.

The eval runner walks fixtures/eval_set/* in mock mode (or api mode),
runs each through the CLI chain (story → prompts → generate → judges →
stitch), captures judge scores + cost + time, appends a row to
fixtures/eval_set/eval_runs.csv.

Mock mode = $0 LLM, $0 Kling, fast. Real mode is per-operator-decision
and not exercised here.

TDD red phase: tests fail with ImportError until eval_runner.py exists.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tmp_eval_set(tmp_path: Path) -> Path:
    """Create a tmp eval_set with 1 minimal fixture project."""
    eval_set = tmp_path / "eval_set"
    fixture = eval_set / "01_minimal" / "inputs"
    fixture.mkdir(parents=True)
    (eval_set / "01_minimal" / "metadata" / "logs").mkdir(parents=True)
    # 3 fake input photos (3 photos = 2 pairs, minimum viable)
    for n in (1, 2, 3):
        (fixture / f"{n}.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    # also drop in extended/ (skip extend stage)
    extended = eval_set / "01_minimal" / "extended"
    extended.mkdir(parents=True)
    for n in (1, 2, 3):
        (extended / f"{n}.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    # metadata
    (eval_set / "01_minimal" / "metadata" / "project.json").write_text(json.dumps({
        "slug": "01_minimal", "name": "Minimal eval fixture",
        "created_at": "2026-04-26",
        "subject": "test", "tone": "neutral", "notes": "",
    }))
    (eval_set / "01_minimal" / "metadata" / "expected_brief.json").write_text(json.dumps({
        "arc_type": "3-act-heroic", "subject": "test", "tone": "neutral", "notes": "",
    }))
    return eval_set


def test_eval_runner_walks_fixture_in_mock_mode(tmp_eval_set):
    """Runner walks 1 fixture in mock mode, appends 1 row to CSV."""
    csv_path = tmp_eval_set / "eval_runs.csv"
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "eval_runner.py"),
         "--label", "test-baseline",
         "--mode", "mock",
         "--eval-set", str(tmp_eval_set),
         "--fixture", "all"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"runner failed: {result.stderr}"
    assert csv_path.is_file(), f"CSV not created at {csv_path}"
    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 1, "expected ≥1 data row in CSV"
    assert rows[0]["fixture_id"] == "01_minimal"
    assert rows[0]["mode"] == "mock"
    assert rows[0]["arc_type"] == "3-act-heroic"


def test_eval_runner_appends_not_overwrites(tmp_eval_set):
    """Two runs → 2 rows in CSV (append, not overwrite)."""
    cmd = [sys.executable, str(REPO_ROOT / "tools" / "eval_runner.py"),
           "--label", "run1", "--mode", "mock",
           "--eval-set", str(tmp_eval_set), "--fixture", "all"]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    cmd[cmd.index("run1")] = "run2"
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)

    csv_path = tmp_eval_set / "eval_runs.csv"
    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    labels = {r["run_label"] for r in rows}
    assert "run1" in labels and "run2" in labels


def test_eval_runner_csv_schema(tmp_eval_set):
    """CSV has the documented columns."""
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "eval_runner.py"),
         "--label", "schema-test", "--mode", "mock",
         "--eval-set", str(tmp_eval_set), "--fixture", "all"],
        check=True, capture_output=True, timeout=120,
    )
    csv_path = tmp_eval_set / "eval_runs.csv"
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
    required_cols = {
        "run_label", "fixture_id", "timestamp", "arc_type", "n_pairs",
        "cost_usd", "wall_time_s", "mode",
    }
    missing = required_cols - set(cols)
    assert not missing, f"missing CSV columns: {missing}"


def test_eval_runner_skips_missing_fixture(tmp_eval_set):
    """Pointing at a non-existent fixture id should fail gracefully (exit code != 0
    OR a clear skip log)."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "eval_runner.py"),
         "--label", "missing", "--mode", "mock",
         "--eval-set", str(tmp_eval_set), "--fixture", "99_nonexistent"],
        capture_output=True, text=True, timeout=60,
    )
    # Either fail explicitly or just not create rows for the missing one.
    csv_path = tmp_eval_set / "eval_runs.csv"
    if csv_path.is_file():
        with csv_path.open() as f:
            rows = list(csv.DictReader(f))
        # No rows for the nonexistent fixture
        assert not any(r.get("fixture_id") == "99_nonexistent" for r in rows)


def test_eval_runner_api_mode_calls_real_generate(tmp_eval_set, monkeypatch):
    """--mode api must pass mode='api' to run_generate, not hard-coded 'mock'."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "eval_runner_under_test", REPO_ROOT / "tools" / "eval_runner.py"
    )
    eval_runner_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eval_runner_mod)  # type: ignore[union-attr]

    recorded: list[str] = []

    def fake_run_generate(project_dir, mode, fal_key=None):
        recorded.append(mode)
        return {}

    import backend.services.generate as gen_mod
    monkeypatch.setattr(gen_mod, "run_generate", fake_run_generate)

    fixture = tmp_eval_set / "01_minimal"
    eval_runner_mod.run_fixture(fixture, label="test-api", mode="api")

    assert recorded, "run_generate was never called"
    assert recorded[0] == "api", f"expected mode='api', got {recorded[0]!r}"
