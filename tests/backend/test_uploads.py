"""Step 5: uploads router (TDD red).

- POST /projects/{id}/uploads  (multipart file) -> 201 { upload_id, filename }
- GET  /projects/{id}/uploads                    -> 200 [list]
- DELETE /projects/{id}/uploads/{filename}       -> 204 | 404
- Non-image content_type rejected with 400.
- Uploads scoped per user; user B can't touch user A's uploads.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.deps import get_db_path, get_storage_root
from backend.main import app

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf"
    b"\xc0\x00\x00\x00\x03\x00\x01\x5c\xcd\xff\x69\x00\x00\x00\x00IEND\xaeB`\x82"
)


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


@pytest.fixture
def project_id(client: TestClient) -> str:
    return client.post("/projects", json={"name": "UploadsTest"}).json()["project_id"]


def _upload(client: TestClient, pid: str, filename: str, data: bytes, ctype: str, user: str = "local"):
    return client.post(
        f"/projects/{pid}/uploads",
        files={"file": (filename, io.BytesIO(data), ctype)},
        headers={"X-User-ID": user},
    )


def test_upload_png_persists_file(client: TestClient, project_id: str, tmp_path: Path) -> None:
    r = _upload(client, project_id, "frame.png", PNG_BYTES, "image/png")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["filename"] == "frame.png"
    on_disk = tmp_path / "pipeline_runs" / "local" / project_id / "sources" / "frame.png"
    assert on_disk.exists()
    assert on_disk.read_bytes() == PNG_BYTES


def test_list_uploads(client: TestClient, project_id: str) -> None:
    _upload(client, project_id, "a.png", PNG_BYTES, "image/png")
    _upload(client, project_id, "b.png", PNG_BYTES, "image/png")
    r = client.get(f"/projects/{project_id}/uploads")
    assert r.status_code == 200
    names = {u["filename"] for u in r.json()}
    assert names == {"a.png", "b.png"}


def test_delete_upload(client: TestClient, project_id: str, tmp_path: Path) -> None:
    _upload(client, project_id, "gone.png", PNG_BYTES, "image/png")
    r = client.delete(f"/projects/{project_id}/uploads/gone.png")
    assert r.status_code == 204
    assert not (tmp_path / "pipeline_runs" / "local" / project_id / "sources" / "gone.png").exists()


def test_delete_missing_upload_returns_404(client: TestClient, project_id: str) -> None:
    assert client.delete(f"/projects/{project_id}/uploads/nope.png").status_code == 404


def test_reject_non_image(client: TestClient, project_id: str) -> None:
    r = _upload(client, project_id, "note.txt", b"hello", "text/plain")
    assert r.status_code == 400


def test_upload_scoped_per_user(client: TestClient) -> None:
    alice_pid = client.post(
        "/projects", json={"name": "AliceProj"}, headers={"X-User-ID": "alice"}
    ).json()["project_id"]
    _upload(client, alice_pid, "secret.png", PNG_BYTES, "image/png", user="alice")
    # Bob cannot list alice's uploads (project not visible to bob)
    r = client.get(f"/projects/{alice_pid}/uploads", headers={"X-User-ID": "bob"})
    assert r.status_code == 404
