"""Step 8: extend stage endpoint (TDD red).

POST /projects/{id}/extend copies outpainted/*.jpg → kling_test/*.jpg in mock mode.
Requires prepare to have produced outpainted/*.jpg first (it writes to the project dir).
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
def project_with_outpainted(client) -> str:
    c, _, _ = client
    pid = c.post("/projects", json={"name": "ExtProj"}).json()["project_id"]
    r = c.post(f"/projects/{pid}/prepare", json={"mode": "mock"})
    assert r.status_code == 202
    return pid


def _job_row(db: Path, job_id: str) -> dict:
    with connect(db) as con:
        r = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(r) if r else None


def test_mock_extend_copies_outpainted_to_kling_test(client, project_with_outpainted: str) -> None:
    c, db, storage = client
    r = c.post(f"/projects/{project_with_outpainted}/extend", json={"mode": "mock"})
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    row = _job_row(db, jid)
    assert row["status"] == "done", row
    kling = storage / "local" / project_with_outpainted / "extended"
    produced = sorted(p.name for p in kling.glob("*.jpg"))
    assert len(produced) == 6, produced


def test_extend_records_mode_in_payload(client, project_with_outpainted: str) -> None:
    c, db, _ = client
    jid = c.post(f"/projects/{project_with_outpainted}/extend", json={"mode": "mock"}).json()["job_id"]
    import json as _json
    row = _job_row(db, jid)
    assert _json.loads(row["payload"])["mode"] == "mock"


def test_extend_for_missing_project_returns_404(client) -> None:
    c, _, _ = client
    assert c.post("/projects/does-not-exist/extend", json={"mode": "mock"}).status_code == 404


def test_extend_before_prepare_fails(client) -> None:
    """Extend without prior prepare → job should land in 'error' status."""
    c, db, _ = client
    pid = c.post("/projects", json={"name": "NoPrep"}).json()["project_id"]
    jid = c.post(f"/projects/{pid}/extend", json={"mode": "mock"}).json()["job_id"]
    row = _job_row(db, jid)
    assert row["status"] == "error"
    assert "extended/_4_3" in row["error"].lower()
