"""Step 6: job runner + polling endpoint (TDD red).

- create_job inserts a row with status='pending'
- run_job_sync transitions pending -> running -> done
- Exceptions raised by the runner_fn are captured; status='error', error text set
- GET /projects/{id}/jobs/{job_id} returns current status, 404 if missing
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db import connect, init_db
from backend.deps import get_db_path, get_storage_root
from backend.main import app
from backend.services import jobs as jobs_svc


@pytest.fixture
def client(tmp_path: Path):
    db = tmp_path / "index.db"
    storage = tmp_path / "projects"
    storage.mkdir()
    app.dependency_overrides[get_db_path] = lambda: db
    app.dependency_overrides[get_storage_root] = lambda: storage
    try:
        with TestClient(app) as c:
            yield c, db
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def project_id(client) -> str:
    c, _ = client
    return c.post("/projects", json={"name": "JobProj"}).json()["project_id"]


def _row(db_path: Path, job_id: str) -> dict:
    with connect(db_path) as con:
        r = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(r) if r else None


def test_create_job_writes_pending_row(client, project_id: str) -> None:
    _, db = client
    jid = jobs_svc.create_job(db, project_id=project_id, user_id="local", kind="prepare", payload={"mode": "mock"})
    row = _row(db, jid)
    assert row["status"] == "pending"
    assert row["kind"] == "prepare"
    assert row["project_id"] == project_id
    assert row["user_id"] == "local"


def test_run_job_sync_transitions_to_done(client, project_id: str) -> None:
    _, db = client
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return {"produced": 6}

    jid = jobs_svc.create_job(db, project_id=project_id, user_id="local", kind="prepare", payload={"x": 1})
    jobs_svc.run_job_sync(db, jid, runner)
    row = _row(db, jid)
    assert row["status"] == "done"
    assert row["error"] is None
    # runner received the payload as kwargs
    assert calls[0] == {"x": 1}


def test_run_job_sync_captures_exception(client, project_id: str) -> None:
    _, db = client

    def boom(**kwargs):
        raise RuntimeError("kaboom")

    jid = jobs_svc.create_job(db, project_id=project_id, user_id="local", kind="prepare", payload={})
    jobs_svc.run_job_sync(db, jid, boom)
    row = _row(db, jid)
    assert row["status"] == "error"
    assert "kaboom" in row["error"]


def test_poll_endpoint_returns_status(client, project_id: str) -> None:
    c, db = client
    jid = jobs_svc.create_job(db, project_id=project_id, user_id="local", kind="prepare", payload={})
    r = c.get(f"/projects/{project_id}/jobs/{jid}")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_poll_endpoint_404_for_missing(client, project_id: str) -> None:
    c, _ = client
    r = c.get(f"/projects/{project_id}/jobs/does-not-exist")
    assert r.status_code == 404
