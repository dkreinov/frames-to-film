"""Step 2: GET /projects/{id}/outputs/{stage} (TDD red).

Returns the sorted list of file names inside <project>/<stage>/. Does NOT
stream files (that's /artifacts/). Phase 4 Prepare needs this to render
the post-run thumbnail grid.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
            yield c, storage
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def project_prepared(client) -> str:
    c, _ = client
    pid = c.post("/projects", json={"name": "OutputsTest"}).json()["project_id"]
    assert c.post(f"/projects/{pid}/prepare", json={"mode": "mock"}).status_code == 202
    return pid


def test_list_outputs_after_prepare(client, project_prepared: str) -> None:
    c, _ = client
    r = c.get(f"/projects/{project_prepared}/outputs/outpainted")
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "outpainted"
    assert sorted(body["outputs"]) == ["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg", "6.jpg"]


def test_list_outputs_missing_stage_returns_404(client) -> None:
    c, _ = client
    pid = c.post("/projects", json={"name": "Empty"}).json()["project_id"]
    r = c.get(f"/projects/{pid}/outputs/outpainted")
    assert r.status_code == 404


def test_list_outputs_path_escape_blocked(client, project_prepared: str) -> None:
    c, _ = client
    r = c.get(f"/projects/{project_prepared}/outputs/..%2F..%2Fetc")
    assert r.status_code in (400, 403, 404)


def test_list_outputs_scoped_to_user(client) -> None:
    c, _ = client
    pid = c.post("/projects", json={"name": "A"}, headers={"X-User-ID": "alice"}).json()["project_id"]
    c.post(f"/projects/{pid}/prepare", json={"mode": "mock"}, headers={"X-User-ID": "alice"})
    r = c.get(f"/projects/{pid}/outputs/outpainted", headers={"X-User-ID": "bob"})
    assert r.status_code == 404
