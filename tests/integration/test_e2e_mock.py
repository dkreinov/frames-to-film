"""Step 14: end-to-end mock pipeline smoke test.

Drives the full FastAPI surface — create project → upload 6 frames →
prepare → extend → generate → stitch → poll each job to done → download
full_movie.mp4. Uses TestClient (no live uvicorn, no port flake).
"""
from __future__ import annotations

import io
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


def _wait_done(db: Path, job_id: str) -> str:
    """TestClient runs BackgroundTasks synchronously before returning to the
    test, so polling isn't needed — we just read the final row."""
    with connect(db) as con:
        row = con.execute("SELECT status, error FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    assert row is not None, f"job {job_id} not found"
    return dict(row)["status"]


def test_full_mock_pipeline_end_to_end(client) -> None:
    c, db, storage = client

    # 1. health check
    assert c.get("/health").json() == {"status": "ok"}

    # 2. create project
    project = c.post("/projects", json={"name": "CosmoE2E"}).json()
    pid = project["project_id"]
    assert project["user_id"] == "local"

    # 3. upload the 6 Cosmo frames
    for frame in sorted(FIXTURE_DIR.glob("frame_*_gemini.png")):
        r = c.post(
            f"/projects/{pid}/uploads",
            files={"file": (frame.name, io.BytesIO(frame.read_bytes()), "image/png")},
        )
        assert r.status_code == 201, r.text
    assert len(c.get(f"/projects/{pid}/uploads").json()) == 6

    # 4. run all four stage jobs and assert each lands in 'done'
    for stage in ("prepare", "extend", "generate", "stitch"):
        r = c.post(f"/projects/{pid}/{stage}", json={"mode": "mock"})
        assert r.status_code == 202, f"{stage} POST -> {r.status_code}: {r.text}"
        job_id = r.json()["job_id"]
        poll = c.get(f"/projects/{pid}/jobs/{job_id}").json()
        assert poll["status"] == "done", (stage, poll)

    # 5. mark a segment as winner (review endpoint)
    r = c.post(
        f"/projects/{pid}/segments/seg_1_to_2/review",
        json={"verdict": "winner"},
    )
    assert r.status_code == 200

    # 6. download full movie
    r = c.get(f"/projects/{pid}/download")
    assert r.status_code == 200
    assert r.content[4:8] == b"ftyp"
    assert len(r.content) > 5000
