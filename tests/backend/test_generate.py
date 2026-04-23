"""Step 9: generate stage (TDD red).

POST /projects/{id}/generate produces N-1 stub mp4s for N kling_test frames.
Each stub is a valid mp4 (ffprobe-parseable).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db import connect
from backend.deps import get_db_path, get_storage_root
from backend.main import app
from backend.services import generate as generate_svc
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
def project_ready_for_generate(client) -> str:
    c, _, _ = client
    pid = c.post("/projects", json={"name": "GenProj"}).json()["project_id"]
    assert c.post(f"/projects/{pid}/prepare", json={"mode": "mock"}).status_code == 202
    assert c.post(f"/projects/{pid}/extend", json={"mode": "mock"}).status_code == 202
    return pid


def _job_row(db: Path, job_id: str) -> dict:
    with connect(db) as con:
        r = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(r) if r else None


def test_mock_generate_creates_n_minus_1_stubs(client, project_ready_for_generate: str) -> None:
    c, db, storage = client
    r = c.post(f"/projects/{project_ready_for_generate}/generate", json={"mode": "mock"})
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    row = _job_row(db, jid)
    assert row["status"] == "done", row
    videos = storage / "local" / project_ready_for_generate / "kling_test" / "videos"
    stubs = sorted(videos.glob("seg_*.mp4"))
    assert len(stubs) == 5, [s.name for s in stubs]


def test_each_stub_is_valid_mp4(client, project_ready_for_generate: str) -> None:
    c, _, storage = client
    c.post(f"/projects/{project_ready_for_generate}/generate", json={"mode": "mock"})
    videos = storage / "local" / project_ready_for_generate / "kling_test" / "videos"
    ffprobe = generate_svc.FFMPEG_BIN.parent / "ffprobe.exe"
    if not ffprobe.exists():
        # ffprobe bundled alongside ffmpeg in newer builds; fall back to header-magic check
        for p in videos.glob("seg_*.mp4"):
            data = p.read_bytes()
            assert len(data) > 1000, f"{p.name} too small"
            assert b"ftyp" in data[:32], f"{p.name} lacks mp4 ftyp atom"
        return
    for p in videos.glob("seg_*.mp4"):
        result = subprocess.run(
            [str(ffprobe), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert float(result.stdout.strip()) > 0


def test_generate_without_extend_returns_error_job(client) -> None:
    c, db, _ = client
    pid = c.post("/projects", json={"name": "NoExt"}).json()["project_id"]
    jid = c.post(f"/projects/{pid}/generate", json={"mode": "mock"}).json()["job_id"]
    row = _job_row(db, jid)
    assert row["status"] == "error"


def test_generate_scoped_to_user(client) -> None:
    c, _, _ = client
    pid = c.post("/projects", json={"name": "A"}, headers={"X-User-ID": "alice"}).json()["project_id"]
    r = c.post(f"/projects/{pid}/generate", json={"mode": "mock"}, headers={"X-User-ID": "bob"})
    assert r.status_code == 404
