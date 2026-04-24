"""Phase 5 Sub-Plan 1 tests: generate-videos accepts mode='web'.

Step 2 only pins router acceptance (202). Step 4 extends this file with
the full graceful-failure path (job status='error' with Phase 5 Sub-Plan 2
message, NOT a 500 crash, NOT a ValueError).
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
def project_ready(client) -> str:
    c, _, _ = client
    pid = c.post("/projects", json={"name": "WebModeProj"}).json()["project_id"]
    assert c.post(f"/projects/{pid}/prepare", json={"mode": "mock"}).status_code == 202
    assert c.post(f"/projects/{pid}/extend", json={"mode": "mock"}).status_code == 202
    return pid


def _job_row(db: Path, job_id: str) -> dict:
    with connect(db) as con:
        r = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(r) if r else None


def test_generate_web_mode_is_accepted_by_router(client, project_ready: str) -> None:
    """Router accepts mode='web'. Runner-side dispatch is Step 4 territory."""
    c, _, _ = client
    r = c.post(f"/projects/{project_ready}/generate", json={"mode": "web"})
    assert r.status_code == 202, r.text
    assert "job_id" in r.json()


def test_generate_rejects_unknown_mode(client, project_ready: str) -> None:
    """Literal['mock','api','web'] — anything else is a 422 at validation."""
    c, _, _ = client
    r = c.post(f"/projects/{project_ready}/generate", json={"mode": "quantum"})
    assert r.status_code == 422
