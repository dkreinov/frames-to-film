"""Step 7: prepare stage endpoint (TDD red).

POST /projects/{id}/prepare  (mode=mock|api) -> 202 {job_id}
Mock mode copies frame_*.png from the fixture dir to <project>/outpainted/*.jpg.
Job row transitions to 'done' after the background task completes.
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
def project_id(client) -> str:
    c, _, _ = client
    return c.post("/projects", json={"name": "PrepProj"}).json()["project_id"]


def _job_row(db: Path, job_id: str) -> dict:
    with connect(db) as con:
        r = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(r) if r else None


def test_mock_prepare_copies_fixture_frames(client, project_id: str) -> None:
    c, db, storage = client
    r = c.post(f"/projects/{project_id}/prepare", json={"mode": "mock"})
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    row = _job_row(db, jid)
    assert row["status"] == "done", row
    out_dir = storage / "local" / project_id / "outpainted"
    produced = sorted(p.name for p in out_dir.glob("*.jpg"))
    assert len(produced) == 6, produced


def test_prepare_job_records_mode_in_payload(client, project_id: str) -> None:
    c, db, _ = client
    r = c.post(f"/projects/{project_id}/prepare", json={"mode": "mock"})
    jid = r.json()["job_id"]
    row = _job_row(db, jid)
    import json as _json
    payload = _json.loads(row["payload"])
    assert payload["mode"] == "mock"


def test_prepare_for_missing_project_returns_404(client) -> None:
    c, _, _ = client
    assert c.post("/projects/does-not-exist/prepare", json={"mode": "mock"}).status_code == 404


def test_prepare_scoped_to_user(client) -> None:
    c, _, _ = client
    pid = c.post("/projects", json={"name": "A"}, headers={"X-User-ID": "alice"}).json()["project_id"]
    # bob can't trigger alice's prepare
    r = c.post(f"/projects/{pid}/prepare", json={"mode": "mock"}, headers={"X-User-ID": "bob"})
    assert r.status_code == 404
