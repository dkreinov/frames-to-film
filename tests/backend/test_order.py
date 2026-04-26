"""Step 2: PUT/GET /projects/{id}/order (TDD red).

Writes/reads <project>/order.json. Phase 4 Storyboard sub-plan persists
the user's drag-drop ordering of frames here.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.deps import get_db_path, get_storage_root
from backend.main import app


@pytest.fixture
def client(tmp_path: Path):
    db = tmp_path / "index.db"
    storage = tmp_path / "projects"
    storage.mkdir()
    app.dependency_overrides[get_db_path] = lambda: db
    app.dependency_overrides[get_storage_root] = lambda: storage
    try:
        with TestClient(app) as c:
            yield c, storage
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def project_id(client) -> str:
    c, _ = client
    return c.post("/projects", json={"name": "OrderTest"}).json()["project_id"]


def test_put_writes_order_json(client, project_id: str) -> None:
    c, storage = client
    r = c.put(
        f"/projects/{project_id}/order",
        json={"order": ["1.jpg", "3.jpg", "2.jpg"]},
    )
    assert r.status_code == 200, r.text
    on_disk = json.loads((storage / "local" / project_id / "metadata" / "order.json").read_text())
    assert on_disk == {"order": ["1.jpg", "3.jpg", "2.jpg"]}


def test_get_reads_order_json(client, project_id: str) -> None:
    c, _ = client
    c.put(f"/projects/{project_id}/order", json={"order": ["a.jpg", "b.jpg"]})
    r = c.get(f"/projects/{project_id}/order")
    assert r.status_code == 200
    assert r.json() == {"order": ["a.jpg", "b.jpg"]}


def test_get_404_before_any_put(client, project_id: str) -> None:
    c, _ = client
    assert c.get(f"/projects/{project_id}/order").status_code == 404


def test_put_rejects_non_string_entries(client, project_id: str) -> None:
    c, _ = client
    r = c.put(f"/projects/{project_id}/order", json={"order": [1, 2, 3]})
    assert r.status_code == 422  # pydantic validation


def test_put_rejects_empty_list(client, project_id: str) -> None:
    c, _ = client
    r = c.put(f"/projects/{project_id}/order", json={"order": []})
    assert r.status_code == 400


def test_order_scoped_to_user(client) -> None:
    c, _ = client
    pid = c.post("/projects", json={"name": "A"}, headers={"X-User-ID": "alice"}).json()["project_id"]
    c.put(
        f"/projects/{pid}/order",
        json={"order": ["1.jpg"]},
        headers={"X-User-ID": "alice"},
    )
    r = c.get(f"/projects/{pid}/order", headers={"X-User-ID": "bob"})
    assert r.status_code == 404
