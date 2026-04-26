"""Phase 4 sub-plan 4 Step 3: GET /projects/{id}/videos (TDD).

Lists <project>/clips/raw/seg_*.mp4 in the order implied by
_ordered_frames — so the UI can line pair_key -> mp4 deterministically.
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
            yield c, db, storage
    finally:
        app.dependency_overrides.clear()


def _seed_frames(storage: Path, user: str, pid: str, count: int) -> None:
    from PIL import Image
    d = storage / user / pid / "extended"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        Image.new("RGB", (16, 16), (i * 30, 0, 0)).save(d / f"{i}.jpg", "JPEG")


def _seed_video_stub(storage: Path, user: str, pid: str, name: str) -> None:
    d = storage / user / pid / "clips" / "raw"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(b"\x00\x00\x00\x18ftypmp42")  # enough bytes to be non-empty


def test_get_videos_empty_when_dir_missing(client) -> None:
    c, _, storage = client
    pid = c.post("/projects", json={"name": "V1"}).json()["project_id"]
    _seed_frames(storage, "local", pid, 3)
    r = c.get(f"/projects/{pid}/videos")
    assert r.status_code == 200
    assert r.json() == {"videos": []}


def test_get_videos_returns_ordered_list(client) -> None:
    c, _, storage = client
    pid = c.post("/projects", json={"name": "V2"}).json()["project_id"]
    _seed_frames(storage, "local", pid, 3)
    # Three consecutive pairs, dropped in an order that's NOT numeric.
    _seed_video_stub(storage, "local", pid, "seg_2_to_3.mp4")
    _seed_video_stub(storage, "local", pid, "seg_1_to_2.mp4")
    r = c.get(f"/projects/{pid}/videos")
    assert r.status_code == 200
    body = r.json()
    # Order follows _ordered_frames (numeric by default since no order.json).
    assert body == {
        "videos": [
            {"name": "seg_1_to_2.mp4", "pair_key": "1_to_2"},
            {"name": "seg_2_to_3.mp4", "pair_key": "2_to_3"},
        ]
    }


def test_get_videos_honours_order_json(client) -> None:
    c, _, storage = client
    pid = c.post("/projects", json={"name": "V3"}).json()["project_id"]
    _seed_frames(storage, "local", pid, 3)
    # Save a non-numeric order.
    (storage / "local" / pid / "metadata" / "order.json").parent.mkdir(parents=True, exist_ok=True)
    (storage / "local" / pid / "metadata" / "order.json").write_text(
        json.dumps({"order": ["3.jpg", "1.jpg", "2.jpg"]})
    )
    # With that order, pairs are 3_to_1 and 1_to_2.
    _seed_video_stub(storage, "local", pid, "seg_1_to_2.mp4")
    _seed_video_stub(storage, "local", pid, "seg_3_to_1.mp4")
    r = c.get(f"/projects/{pid}/videos")
    body = r.json()
    assert [v["pair_key"] for v in body["videos"]] == ["3_to_1", "1_to_2"]


def test_get_videos_404_for_stranger(client) -> None:
    c, _, storage = client
    pid = c.post("/projects", json={"name": "V4"}, headers={"X-User-ID": "alice"}).json()["project_id"]
    _seed_frames(storage, "alice", pid, 2)
    _seed_video_stub(storage, "alice", pid, "seg_1_to_2.mp4")
    r = c.get(f"/projects/{pid}/videos", headers={"X-User-ID": "bob"})
    assert r.status_code == 404
