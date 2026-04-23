"""Step 5 + 6: /prompts endpoints (TDD red).

POST /projects/{id}/prompts/generate {"mode":"mock","style":"cinematic"}
 -> 202 {job_id}; job runs to done; prompts.json written.
GET /projects/{id}/prompts -> 200 dict | 404 if not generated yet.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db import connect
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
            yield c, db, storage
    finally:
        app.dependency_overrides.clear()


def _seed_kling_into_project(storage_root: Path, user: str, pid: str, count: int) -> None:
    from PIL import Image
    d = storage_root / user / pid / "kling_test"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        Image.new("RGB", (16, 16), (i * 30, 0, 0)).save(d / f"{i}.jpg", "JPEG")


@pytest.fixture
def project_with_kling(client) -> str:
    c, _, storage = client
    pid = c.post("/projects", json={"name": "PromptsTest"}).json()["project_id"]
    _seed_kling_into_project(storage, "local", pid, 6)
    return pid


def _job_row(db: Path, job_id: str) -> dict:
    with connect(db) as con:
        r = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(r) if r else None


# --- Step 5: POST /prompts/generate ---

def test_mock_prompts_generate_writes_json(client, project_with_kling: str) -> None:
    c, db, storage = client
    r = c.post(
        f"/projects/{project_with_kling}/prompts/generate",
        json={"mode": "mock", "style": "cinematic"},
    )
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    row = _job_row(db, jid)
    assert row["status"] == "done", row
    pj = storage / "local" / project_with_kling / "prompts.json"
    assert pj.is_file()
    data = json.loads(pj.read_text())
    assert set(data.keys()) == {"1_to_2", "2_to_3", "3_to_4", "4_to_5", "5_to_6"}


def test_prompts_generate_missing_project_returns_404(client) -> None:
    c, _, _ = client
    r = c.post(
        "/projects/nope/prompts/generate",
        json={"mode": "mock", "style": "cinematic"},
    )
    assert r.status_code == 404


def test_prompts_generate_scoped_to_user(client) -> None:
    c, _, _ = client
    pid = c.post("/projects", json={"name": "A"}, headers={"X-User-ID": "alice"}).json()["project_id"]
    r = c.post(
        f"/projects/{pid}/prompts/generate",
        json={"mode": "mock", "style": "cinematic"},
        headers={"X-User-ID": "bob"},
    )
    assert r.status_code == 404


# --- Step 6: GET /prompts ---

def test_get_prompts_after_generate(client, project_with_kling: str) -> None:
    c, _, _ = client
    c.post(
        f"/projects/{project_with_kling}/prompts/generate",
        json={"mode": "mock", "style": "nostalgic"},
    )
    r = c.get(f"/projects/{project_with_kling}/prompts")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 5
    from backend.services.prompts import STYLE_PRESETS
    for v in body.values():
        assert v == STYLE_PRESETS["nostalgic"]


def test_get_prompts_before_generate_returns_404(client, project_with_kling: str) -> None:
    c, _, _ = client
    r = c.get(f"/projects/{project_with_kling}/prompts")
    assert r.status_code == 404


def test_get_prompts_scoped_to_user(client) -> None:
    c, _, storage = client
    pid = c.post("/projects", json={"name": "A"}, headers={"X-User-ID": "alice"}).json()["project_id"]
    _seed_kling_into_project(storage, "alice", pid, 3)
    c.post(
        f"/projects/{pid}/prompts/generate",
        json={"mode": "mock"},
        headers={"X-User-ID": "alice"},
    )
    r = c.get(f"/projects/{pid}/prompts", headers={"X-User-ID": "bob"})
    assert r.status_code == 404
