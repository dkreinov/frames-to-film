"""Step 11: stitch stage (TDD red).

POST /projects/{id}/stitch concatenates seg_*.mp4 → full_movie.mp4.
Requires kling_test/ + videos/ to exist (generate run first).
"""
from __future__ import annotations

import json
import unittest.mock as mock
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db import connect
from backend.deps import get_db_path, get_storage_root
from backend.main import app
from backend.services import prepare as prepare_svc
from backend.services.project_schema import METADATA_DIRNAME

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "fake_project"


@pytest.fixture
def client(tmp_path: Path):
    db = tmp_path / "index.db"
    storage = tmp_path / "projects"
    storage.mkdir()
    app.dependency_overrides[get_db_path] = lambda: db
    app.dependency_overrides[get_storage_root] = lambda: storage
    app.dependency_overrides[prepare_svc.get_fixture_root] = lambda: FIXTURE_DIR
    try:
        with TestClient(app) as c:
            yield c, db, storage
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def project_ready_for_stitch(client) -> str:
    c, _, _ = client
    pid = c.post("/projects", json={"name": "StitchProj"}).json()["project_id"]
    assert c.post(f"/projects/{pid}/prepare", json={"mode": "mock"}).status_code == 202
    assert c.post(f"/projects/{pid}/extend", json={"mode": "mock"}).status_code == 202
    assert c.post(f"/projects/{pid}/generate", json={"mode": "mock"}).status_code == 202
    return pid


def _job_row(db: Path, job_id: str) -> dict:
    with connect(db) as con:
        r = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(r) if r else None


def test_mock_stitch_produces_full_movie_mp4(client, project_ready_for_stitch: str) -> None:
    c, db, storage = client
    r = c.post(f"/projects/{project_ready_for_stitch}/stitch", json={"mode": "mock"})
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    row = _job_row(db, jid)
    assert row["status"] == "done", row
    full_movie = storage / "local" / project_ready_for_stitch / "final" / "full_movie.mp4"
    assert full_movie.exists()
    assert full_movie.stat().st_size > 1000


def test_stitch_duration_equals_sum_of_segments(client, project_ready_for_stitch: str) -> None:
    """5 segments × 1s each = ~5s total (stream-copy is exact)."""
    c, _, storage = client
    c.post(f"/projects/{project_ready_for_stitch}/stitch", json={"mode": "mock"})
    full_movie = storage / "local" / project_ready_for_stitch / "final" / "full_movie.mp4"
    # Stream copy is exact — ffprobe to confirm.
    import subprocess
    ffprobe = Path("D:/Programming/olga_movie/tools/ffprobe.exe")
    if not ffprobe.exists():
        pytest.skip("ffprobe not bundled")
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(full_movie)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    duration = float(result.stdout.strip())
    assert 4.5 <= duration <= 5.5, f"duration={duration}"


def test_stitch_without_generate_returns_error_job(client) -> None:
    c, db, _ = client
    pid = c.post("/projects", json={"name": "NoGen"}).json()["project_id"]
    jid = c.post(f"/projects/{pid}/stitch", json={"mode": "mock"}).json()["job_id"]
    row = _job_row(db, jid)
    assert row["status"] == "error"


def test_stitch_scoped_to_user(client) -> None:
    c, _, _ = client
    pid = c.post("/projects", json={"name": "A"}, headers={"X-User-ID": "alice"}).json()["project_id"]
    r = c.post(f"/projects/{pid}/stitch", json={"mode": "mock"}, headers={"X-User-ID": "bob"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Phase 7.7 — story-aware xfade routing tests
# ---------------------------------------------------------------------------

def _seed_story_json(project_dir: Path, device: str = "cross_dissolve") -> None:
    """Write metadata/story.json with 4 pair_intents using the given device."""
    meta = project_dir / METADATA_DIRNAME
    meta.mkdir(parents=True, exist_ok=True)
    story = {
        "arc_paragraph": "Test arc.",
        "pair_intents": [
            {"from": i, "to": i + 1, "device": device, "intent": "test motion"}
            for i in range(1, 5)
        ],
        "arc_type": "life-montage",
    }
    (meta / "story.json").write_text(json.dumps(story), encoding="utf-8")


def test_stitch_with_story_json_invokes_xfade_path(
    client, project_ready_for_stitch: str
) -> None:
    """story.json present → xfade path taken; concat_videos.run NOT called."""
    c, db, storage = client
    project_dir = storage / "local" / project_ready_for_stitch
    _seed_story_json(project_dir, device="cross_dissolve")

    with mock.patch("concat_videos.run") as concat_mock, \
         mock.patch("backend.services.stitch.subprocess") as sp_mock:
        # Fake ffmpeg success: create the output file
        def _fake_run(cmd, **kwargs):
            out = Path(cmd[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"\x00" * 2000)
            result = mock.Mock()
            result.returncode = 0
            return result

        sp_mock.run.side_effect = _fake_run

        r = c.post(f"/projects/{project_ready_for_stitch}/stitch", json={"mode": "mock"})
    assert r.status_code == 202, r.text
    row = _job_row(db, r.json()["job_id"])
    assert row["status"] == "done", row

    # xfade path taken → concat_videos.run was NOT used
    concat_mock.assert_not_called()
    # ffmpeg -filter_complex was invoked
    assert sp_mock.run.called
    cmd = sp_mock.run.call_args[0][0]
    assert "-filter_complex" in cmd


def test_stitch_with_unknown_device_in_story_falls_back_to_fade(
    client, project_ready_for_stitch: str
) -> None:
    """Unknown device in story.json → no crash; filter uses fade (default)."""
    c, db, storage = client
    project_dir = storage / "local" / project_ready_for_stitch
    _seed_story_json(project_dir, device="completely_made_up_device")

    captured_cmds: list[list] = []

    with mock.patch("concat_videos.run"), \
         mock.patch("backend.services.stitch.subprocess") as sp_mock:
        def _fake_run(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            out = Path(cmd[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"\x00" * 2000)
            result = mock.Mock()
            result.returncode = 0
            return result

        sp_mock.run.side_effect = _fake_run

        r = c.post(f"/projects/{project_ready_for_stitch}/stitch", json={"mode": "mock"})
    assert r.status_code == 202, r.text
    row = _job_row(db, r.json()["job_id"])
    assert row["status"] == "done", row

    # filter_complex uses fade (default fallback)
    assert captured_cmds, "ffmpeg was not invoked"
    filter_complex_idx = captured_cmds[0].index("-filter_complex") + 1
    fc_value = captured_cmds[0][filter_complex_idx]
    assert "xfade=transition=fade" in fc_value


def test_stitch_with_hardcut_device_uses_concat_filter(
    client, project_ready_for_stitch: str
) -> None:
    """Empty ffmpeg_xfade device (smash_cut) → concat filter used, no xfade filter."""
    c, db, storage = client
    project_dir = storage / "local" / project_ready_for_stitch
    _seed_story_json(project_dir, device="smash_cut")

    captured_cmds: list[list] = []

    with mock.patch("concat_videos.run"), \
         mock.patch("backend.services.stitch.subprocess") as sp_mock:
        def _fake_run(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            out = Path(cmd[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"\x00" * 2000)
            result = mock.Mock()
            result.returncode = 0
            return result

        sp_mock.run.side_effect = _fake_run

        r = c.post(f"/projects/{project_ready_for_stitch}/stitch", json={"mode": "mock"})
    assert r.status_code == 202, r.text
    row = _job_row(db, r.json()["job_id"])
    assert row["status"] == "done", row

    assert captured_cmds, "ffmpeg was not invoked"
    filter_complex_idx = captured_cmds[0].index("-filter_complex") + 1
    fc_value = captured_cmds[0][filter_complex_idx]
    # smash_cut has empty xfade → concat filter, no xfade keyword
    assert "concat" in fc_value
    assert "xfade" not in fc_value
