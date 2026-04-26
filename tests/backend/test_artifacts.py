"""Step 12: artifact download endpoints (TDD red).

- GET /projects/{id}/artifacts/{stage}/{name}  streams a file from
  <project>/<stage>/.
- GET /projects/{id}/download                  shortcut for full_movie.mp4.
- 404 on missing file.
- 403 on path traversal attempts.
- User-scoped.
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
    storage = tmp_path / "projects"
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
def project_fully_ran(client) -> str:
    c, _ = client
    pid = c.post("/projects", json={"name": "Artifacts"}).json()["project_id"]
    assert c.post(f"/projects/{pid}/prepare", json={"mode": "mock"}).status_code == 202
    assert c.post(f"/projects/{pid}/extend", json={"mode": "mock"}).status_code == 202
    assert c.post(f"/projects/{pid}/generate", json={"mode": "mock"}).status_code == 202
    assert c.post(f"/projects/{pid}/stitch", json={"mode": "mock"}).status_code == 202
    return pid


def test_stream_outpainted_jpg(client, project_fully_ran: str) -> None:
    c, _ = client
    r = c.get(f"/projects/{project_fully_ran}/artifacts/extended/_4_3/1.jpg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")
    assert len(r.content) > 100


def test_download_shortcut_returns_full_movie(client, project_fully_ran: str) -> None:
    c, _ = client
    r = c.get(f"/projects/{project_fully_ran}/download")
    assert r.status_code == 200
    assert r.content[4:8] == b"ftyp"  # valid mp4


def test_missing_artifact_returns_404(client, project_fully_ran: str) -> None:
    c, _ = client
    assert c.get(f"/projects/{project_fully_ran}/artifacts/extended/_4_3/99.jpg").status_code == 404


def test_path_traversal_blocked(client, project_fully_ran: str) -> None:
    """Serving ../../ or /etc/passwd must not be possible."""
    c, _ = client
    r = c.get(f"/projects/{project_fully_ran}/artifacts/extended/_4_3/..%2F..%2F..%2Fsecret.txt")
    assert r.status_code in (403, 404)


def test_artifact_scoped_to_user(client) -> None:
    c, _ = client
    pid = c.post("/projects", json={"name": "Alice"}, headers={"X-User-ID": "alice"}).json()["project_id"]
    c.post(f"/projects/{pid}/prepare", json={"mode": "mock"}, headers={"X-User-ID": "alice"})
    # bob cannot read alice's artifacts
    r = c.get(f"/projects/{pid}/artifacts/extended/_4_3/1.jpg", headers={"X-User-ID": "bob"})
    assert r.status_code == 404
