"""Step 8: de-Olga check — generated prompts must not leak Olga-specific strings.

Runs /prompts/generate with each of the 4 style presets on a non-Olga
project (Cosmo fixture) and asserts zero hits of the known Olga-specific
phrasing across all resulting prompts.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.deps import get_db_path, get_storage_root
from backend.main import app
from backend.services import prepare as prepare_svc

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "fake_project"

# Strings that MUST NOT appear in any generated prompt for a non-Olga project.
OLGA_BLOCKLIST_CASE_INSENSITIVE = [
    "olga",
    "olia",
    "childhood b&w studio",
    "childhood (b&w",  # the section comment phrasing
    "sepia portrait",
    "wedding chuppah",
    "ketubah",
    "fairy-light backdrop",
]


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
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("style", ["cinematic", "nostalgic", "vintage", "playful"])
def test_no_olga_leakage_in_style(client: TestClient, style: str) -> None:
    # create project + run prepare/extend so kling_test/*.jpg exists
    pid = client.post("/projects", json={"name": f"DeOlgaTest-{style}"}).json()["project_id"]
    assert client.post(f"/projects/{pid}/prepare", json={"mode": "mock"}).status_code == 202
    assert client.post(f"/projects/{pid}/extend",  json={"mode": "mock"}).status_code == 202

    # generate prompts
    r = client.post(
        f"/projects/{pid}/prompts/generate",
        json={"mode": "mock", "style": style},
    )
    assert r.status_code == 202, r.text

    # fetch
    r = client.get(f"/projects/{pid}/prompts")
    assert r.status_code == 200
    prompts = r.json()
    assert len(prompts) == 5

    # blocklist check (case-insensitive across all prompts)
    joined = " ".join(prompts.values()).lower()
    for banned in OLGA_BLOCKLIST_CASE_INSENSITIVE:
        assert banned not in joined, (
            f"style={style}: banned phrase {banned!r} leaked into generated prompts: {prompts}"
        )
