"""Step 4: projects CRUD (TDD red).

Contract:
- POST /projects -> 201 { project_id, name, user_id, created_at }
- GET /projects -> 200 [list scoped by X-User-ID header]
- GET /projects/{id} -> 200 | 404
- DELETE /projects/{id} -> 204 | 404
- X-User-ID header defaults to "local"; rows are isolated per user.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.deps import get_db_path, get_storage_root
from backend.main import app


@pytest.fixture
def client(tmp_path: Path):
    db = tmp_path / "index.db"
    storage = tmp_path / "pipeline_runs"
    storage.mkdir()
    app.dependency_overrides[get_db_path] = lambda: db
    app.dependency_overrides[get_storage_root] = lambda: storage
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_create_project_returns_201_and_row(client: TestClient) -> None:
    r = client.post("/projects", json={"name": "Cosmo"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Cosmo"
    assert body["user_id"] == "local"
    assert body["project_id"]


def test_list_projects_is_user_scoped(client: TestClient) -> None:
    client.post("/projects", json={"name": "A"}, headers={"X-User-ID": "alice"})
    client.post("/projects", json={"name": "B"}, headers={"X-User-ID": "bob"})
    r_alice = client.get("/projects", headers={"X-User-ID": "alice"})
    r_bob = client.get("/projects", headers={"X-User-ID": "bob"})
    assert {p["name"] for p in r_alice.json()} == {"A"}
    assert {p["name"] for p in r_bob.json()} == {"B"}


def test_get_project_by_id(client: TestClient) -> None:
    created = client.post("/projects", json={"name": "Pixar"}).json()
    r = client.get(f"/projects/{created['project_id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Pixar"


def test_get_missing_project_returns_404(client: TestClient) -> None:
    assert client.get("/projects/does-not-exist").status_code == 404


def test_delete_project(client: TestClient) -> None:
    created = client.post("/projects", json={"name": "Temp"}).json()
    pid = created["project_id"]
    assert client.delete(f"/projects/{pid}").status_code == 204
    assert client.get(f"/projects/{pid}").status_code == 404


def test_user_cannot_access_other_users_project(client: TestClient) -> None:
    created = client.post(
        "/projects", json={"name": "Private"}, headers={"X-User-ID": "alice"}
    ).json()
    r = client.get(
        f"/projects/{created['project_id']}", headers={"X-User-ID": "bob"}
    )
    assert r.status_code == 404
