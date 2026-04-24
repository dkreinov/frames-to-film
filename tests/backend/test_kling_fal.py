"""Phase 5 Sub-Plan 2 Step 5: kling_fal adapter — mocked HTTP.

Authentic test (plan-skill #9): each test exercises the real adapter
pipeline. We stub `requests.post` / `requests.get` at the adapter's
import site — if someone later renames a payload key or auth header,
the stubbed side-effect asserts will fail and the test breaks.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import requests

from backend.services import kling_fal


def _fixture_jpg(tmp_path: Path, name: str, payload: bytes = b"\xff\xd8\xff\xe0") -> Path:
    # Tiny valid-ish jpeg header — enough for the base64 encode path.
    p = tmp_path / name
    p.write_bytes(payload)
    return p


class _FakeResponse:
    def __init__(self, json_data=None, content=b"", status_code=200):
        self._json = json_data or {}
        self.content = content
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


def test_generate_pair_happy_path(monkeypatch, tmp_path):
    """Submit → poll (1 wait) → result URL → download. Asserts payload +
    auth header shapes exactly so any drift fails loudly."""
    image_a = _fixture_jpg(tmp_path, "a.jpg")
    image_b = _fixture_jpg(tmp_path, "b.jpg")
    fake_mp4 = b"\x00\x00\x00 ftypmp42" + b"x" * 5000

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(("POST", url, headers, json))
        assert url == kling_fal.SUBMIT_URL
        assert headers["Authorization"] == "Key test-fal-key"
        assert headers["Content-Type"] == "application/json"
        assert json["image_url"].startswith("data:image/jpeg;base64,")
        assert json["end_image_url"].startswith("data:image/jpeg;base64,")
        assert json["prompt"] == "Smooth morph A to B"
        assert json["duration"] == "5"
        assert json["generate_audio"] is False
        return _FakeResponse(json_data={"request_id": "req-123"})

    get_responses = iter(
        [
            _FakeResponse(json_data={"status": "IN_PROGRESS"}),
            _FakeResponse(json_data={"status": "COMPLETED"}),
            _FakeResponse(json_data={"video": {"url": "https://cdn/fake.mp4"}}),
            _FakeResponse(content=fake_mp4),
        ]
    )

    def fake_get(url, headers=None, timeout=None):
        calls.append(("GET", url, headers, None))
        # Status + result endpoints require auth; the final mp4 URL is a
        # CDN pre-signed URL — no headers sent on download.
        if "/requests/" in url:
            assert headers["Authorization"] == "Key test-fal-key"
        return next(get_responses)

    # No-op the sleeps so the test runs fast.
    monkeypatch.setattr(kling_fal.time, "sleep", lambda s: None)
    monkeypatch.setattr(kling_fal.requests, "post", fake_post)
    monkeypatch.setattr(kling_fal.requests, "get", fake_get)

    out = kling_fal.generate_pair(
        image_a, image_b, "Smooth morph A to B", fal_key="test-fal-key"
    )

    assert out == fake_mp4
    # Submit + 2 status polls + 1 result + 1 download.
    assert [c[0] for c in calls] == ["POST", "GET", "GET", "GET", "GET"]
    assert "/requests/req-123/status" in calls[1][1]
    assert calls[3][1] == f"{kling_fal.QUEUE_BASE}/{kling_fal.MODEL_ID}/requests/req-123"


def test_generate_pair_raises_on_fal_failure(monkeypatch, tmp_path):
    """FAILED status raises RuntimeError (not silently returns empty)."""
    image_a = _fixture_jpg(tmp_path, "a.jpg")
    image_b = _fixture_jpg(tmp_path, "b.jpg")

    monkeypatch.setattr(kling_fal.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        kling_fal.requests,
        "post",
        lambda *a, **kw: _FakeResponse(json_data={"request_id": "req-fail"}),
    )
    monkeypatch.setattr(
        kling_fal.requests,
        "get",
        lambda *a, **kw: _FakeResponse(json_data={"status": "FAILED"}),
    )

    with pytest.raises(RuntimeError, match="FAILED"):
        kling_fal.generate_pair(image_a, image_b, "x", fal_key="k")


def test_generate_pair_custom_duration(monkeypatch, tmp_path):
    """duration kwarg reaches the submit payload."""
    image_a = _fixture_jpg(tmp_path, "a.jpg")
    image_b = _fixture_jpg(tmp_path, "b.jpg")

    seen_payload = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen_payload.update(json)
        return _FakeResponse(json_data={"request_id": "req-x"})

    monkeypatch.setattr(kling_fal.time, "sleep", lambda s: None)
    monkeypatch.setattr(kling_fal.requests, "post", fake_post)
    monkeypatch.setattr(
        kling_fal.requests,
        "get",
        lambda url, **kw: _FakeResponse(
            json_data={"status": "COMPLETED"} if "status" in url else {"video": {"url": "u"}}
        ),
    )
    # Cover the download too so the full pipeline runs.
    orig_download = kling_fal._download
    monkeypatch.setattr(kling_fal, "_download", lambda url: b"fake")

    kling_fal.generate_pair(image_a, image_b, "x", fal_key="k", duration=10)
    assert seen_payload["duration"] == "10"

    # Restore (test isolation hygiene; monkeypatch does this automatically
    # but we reference orig_download to silence the unused-var warning).
    assert orig_download is not None
