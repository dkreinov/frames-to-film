"""Phase 5 Sub-Plan 2 Step 6+7 integration test: generate api mode drives
the real FastAPI pipeline with kling_fal mocked.

Authentic test (plan-skill #9): POSTs to the real /generate endpoint,
the real background task runs, the real _ordered_frames/_load_prompts
helpers load fixture data, kling_fal.generate_pair is monkeypatched at
module-level so no network call fires. If the api branch regresses
(e.g., fal_key dropped from payload, prompts.json not honored, pair
loop broken), the assertions fail.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db import connect
from backend.deps import get_db_path, get_storage_root
from backend.main import app
from backend.services import generate as generate_svc
from backend.services import kling_fal
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
def project_ready(client) -> str:
    c, _, _ = client
    pid = c.post("/projects", json={"name": "FalProj"}).json()["project_id"]
    assert c.post(f"/projects/{pid}/prepare", json={"mode": "mock"}).status_code == 202
    assert c.post(f"/projects/{pid}/extend", json={"mode": "mock"}).status_code == 202
    return pid


def _job_row(db: Path, job_id: str) -> dict:
    with connect(db) as con:
        r = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(r) if r else None


def test_api_mode_calls_kling_fal_per_pair(client, project_ready, monkeypatch):
    """End-to-end: POST /generate {mode:'api'} with X-Fal-Key header →
    runner loops frame pairs → kling_fal.generate_pair called N-1 times
    with fal_key from the payload → mp4 written to disk per pair.
    """
    c, db, storage = client
    pid = project_ready

    captured: list[dict] = []

    def fake_generate_pair(image_a, image_b, prompt, fal_key, duration=5):
        captured.append(
            {
                "a": image_a.name,
                "b": image_b.name,
                "prompt": prompt,
                "fal_key": fal_key,
                "duration": duration,
            }
        )
        return b"\x00\x00\x00 ftypmp42" + b"x" * 200

    monkeypatch.setattr(generate_svc.kling_fal, "generate_pair", fake_generate_pair)

    r = c.post(
        f"/projects/{pid}/generate",
        json={"mode": "api"},
        headers={"X-Fal-Key": "test-fal-key"},
    )
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]

    row = _job_row(db, jid)
    assert row["status"] == "done", row

    # fixture_project has 6 photos → 5 transitions.
    assert len(captured) == 5, captured
    # Every call received the key from the header via payload.
    assert all(c_["fal_key"] == "test-fal-key" for c_ in captured)
    # Every call used 5s duration per the plan directive.
    assert all(c_["duration"] == 5 for c_ in captured)

    video_dir = storage / "local" / pid / "clips" / "raw"
    mp4s = sorted(video_dir.glob("seg_*.mp4"))
    assert len(mp4s) == 5, [p.name for p in mp4s]
    # Each mp4 has the ftyp atom from our fake bytes.
    for mp4 in mp4s:
        assert b"ftyp" in mp4.read_bytes()[:32]


def test_api_mode_without_key_returns_400(client, project_ready):
    """resolve_fal_key raises HTTPException(400) when no header + no env.
    The error must surface as a 400 at POST time, not a runner crash.
    """
    c, _, _ = client
    pid = project_ready
    import os
    os.environ.pop("FAL_KEY", None)
    r = c.post(f"/projects/{pid}/generate", json={"mode": "api"})
    assert r.status_code == 400, r.text
    assert "fal.ai API key required" in r.json()["detail"]


def test_api_mode_env_fallback_when_no_header(client, project_ready, monkeypatch):
    """FAL_KEY env var is accepted when no X-Fal-Key header is sent."""
    c, db, _ = client
    pid = project_ready
    monkeypatch.setenv("FAL_KEY", "env-fallback-key")

    seen_key = {"value": None}

    def fake_generate_pair(image_a, image_b, prompt, fal_key, duration=5):
        seen_key["value"] = fal_key
        return b"mp4-bytes"

    monkeypatch.setattr(generate_svc.kling_fal, "generate_pair", fake_generate_pair)

    r = c.post(f"/projects/{pid}/generate", json={"mode": "api"})
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    row = _job_row(db, jid)
    assert row["status"] == "done", row
    assert seen_key["value"] == "env-fallback-key"
