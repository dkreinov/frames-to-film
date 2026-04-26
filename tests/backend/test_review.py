"""Step 10: review endpoint (TDD red).

POST /projects/{id}/segments/{seg_id}/review writes a verdict row.
Synchronous — no job. Overwrites prior verdict on same seg_id.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db import connect
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
            yield c, db
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def project_id(client) -> str:
    c, _ = client
    return c.post("/projects", json={"name": "RevProj"}).json()["project_id"]


def _segments(db: Path, project_id: str, user_id: str = "local") -> list[dict]:
    with connect(db) as con:
        rows = con.execute(
            "SELECT * FROM segments WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchall()
    return [dict(r) for r in rows]


def test_write_winner(client, project_id: str) -> None:
    c, db = client
    r = c.post(
        f"/projects/{project_id}/segments/seg_1_to_2/review",
        json={"verdict": "winner"},
    )
    assert r.status_code == 200, r.text
    rows = _segments(db, project_id)
    assert len(rows) == 1
    assert rows[0]["verdict"] == "winner"
    assert rows[0]["seg_id"] == "seg_1_to_2"


def test_write_redo_with_notes(client, project_id: str) -> None:
    c, db = client
    r = c.post(
        f"/projects/{project_id}/segments/seg_2_to_3/review",
        json={"verdict": "redo", "notes": "blurry at transition"},
    )
    assert r.status_code == 200
    rows = _segments(db, project_id)
    assert rows[0]["verdict"] == "redo"
    assert rows[0]["notes"] == "blurry at transition"


def test_overwrite_prior_verdict(client, project_id: str) -> None:
    c, db = client
    c.post(
        f"/projects/{project_id}/segments/seg_3_to_4/review",
        json={"verdict": "redo"},
    )
    c.post(
        f"/projects/{project_id}/segments/seg_3_to_4/review",
        json={"verdict": "winner"},
    )
    rows = _segments(db, project_id)
    assert len(rows) == 1
    assert rows[0]["verdict"] == "winner"


def test_review_missing_project_returns_404(client) -> None:
    c, _ = client
    r = c.post(
        "/projects/does-not-exist/segments/seg_1_to_2/review",
        json={"verdict": "winner"},
    )
    assert r.status_code == 404


def test_review_scoped_to_user(client) -> None:
    c, _ = client
    pid = c.post("/projects", json={"name": "A"}, headers={"X-User-ID": "alice"}).json()["project_id"]
    r = c.post(
        f"/projects/{pid}/segments/seg_1_to_2/review",
        json={"verdict": "winner"},
        headers={"X-User-ID": "bob"},
    )
    assert r.status_code == 404


# --- Phase 4 sub-plan 5 Step 1: GET /projects/{id}/segments ---

def test_list_segments_empty_when_no_reviews(client, project_id: str) -> None:
    c, _ = client
    r = c.get(f"/projects/{project_id}/segments")
    assert r.status_code == 200
    assert r.json() == {"segments": []}


def test_list_segments_after_reviews_returns_sorted(client, project_id: str) -> None:
    c, _ = client
    # Review in reverse seg_id order to prove sorting.
    c.post(f"/projects/{project_id}/segments/seg_2_to_3/review", json={"verdict": "redo"})
    c.post(
        f"/projects/{project_id}/segments/seg_1_to_2/review",
        json={"verdict": "winner", "notes": "great"},
    )
    r = c.get(f"/projects/{project_id}/segments")
    assert r.status_code == 200
    body = r.json()
    assert [s["seg_id"] for s in body["segments"]] == ["seg_1_to_2", "seg_2_to_3"]
    assert body["segments"][0]["verdict"] == "winner"
    assert body["segments"][0]["notes"] == "great"
    assert body["segments"][1]["verdict"] == "redo"
    # each row has updated_at ISO string
    assert body["segments"][0]["updated_at"]


def test_list_segments_404_for_stranger(client) -> None:
    c, _ = client
    pid = c.post(
        "/projects", json={"name": "A"}, headers={"X-User-ID": "alice"}
    ).json()["project_id"]
    c.post(
        f"/projects/{pid}/segments/seg_1_to_2/review",
        json={"verdict": "winner"},
        headers={"X-User-ID": "alice"},
    )
    r = c.get(f"/projects/{pid}/segments", headers={"X-User-ID": "bob"})
    assert r.status_code == 404
