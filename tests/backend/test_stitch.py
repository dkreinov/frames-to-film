"""Step 11: stitch stage (TDD red).

POST /projects/{id}/stitch concatenates seg_*.mp4 → full_movie.mp4.
Requires kling_test/ + videos/ to exist (generate run first).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db import connect
from backend.deps import get_db_path, get_storage_root
from backend.main import app
from backend.services import prepare as prepare_svc

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "fake_project"


@pytest.fixture
def client(tmp_path: Path):
    db = tmp_path / "index.db"
    storage = tmp_path / "pipeline_runs"
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
    full_movie = storage / "local" / project_ready_for_stitch / "kling_test" / "videos" / "full_movie.mp4"
    assert full_movie.exists()
    assert full_movie.stat().st_size > 1000


def test_stitch_duration_equals_sum_of_segments(client, project_ready_for_stitch: str) -> None:
    """5 segments × 1s each = ~5s total (stream-copy is exact)."""
    c, _, storage = client
    c.post(f"/projects/{project_ready_for_stitch}/stitch", json={"mode": "mock"})
    full_movie = storage / "local" / project_ready_for_stitch / "kling_test" / "videos" / "full_movie.mp4"
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
