"""fal.ai Kling O3 first-last-frame adapter.

Thin wrapper around fal.ai's queue REST API for the Kling O3 standard
image-to-video endpoint. Submit → poll → download the mp4.

Phase 5 Sub-Plan 2 adapter. Replaces the legacy `generate_all_videos.py`
direct-Kling JWT flow with a simpler `Authorization: Key <FAL_KEY>` path.

Endpoint docs: https://fal.ai/models/fal-ai/kling-video/o3/standard/image-to-video
Auth docs:     https://fal.ai/docs/model-endpoints/queue
"""
from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

MODEL_ID = "fal-ai/kling-video/o3/standard/image-to-video"
QUEUE_BASE = "https://queue.fal.run"
# Base path for status/result URLs — fal.ai omits the variant suffix
# (/o3/standard/…) from those paths even when the submit URL includes it.
_STATUS_BASE = f"{QUEUE_BASE}/fal-ai/kling-video/requests"
SUBMIT_URL = f"{QUEUE_BASE}/{MODEL_ID}"

# Polling schedule: fal.ai Kling O3 typically takes 1-3 minutes per clip.
# Start with short intervals to catch fast completions, ramp to 15s.
_POLL_INTERVALS_S = [3, 5, 8, 10, 10, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15]


def _image_to_data_uri(path: Path) -> str:
    """fal.ai accepts both HTTPS URLs and base64 data URIs.

    Local files → data URI. Keeps the adapter self-contained (no upload
    step, no presigned URL dance).
    """
    ext = path.suffix.lower().lstrip(".") or "jpeg"
    if ext == "jpg":
        ext = "jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/{ext};base64,{b64}"


def _auth_headers(fal_key: str) -> dict:
    return {
        "Authorization": f"Key {fal_key}",
        "Content-Type": "application/json",
    }


def _submit(
    image_a: Path,
    image_b: Path,
    prompt: str,
    fal_key: str,
    duration: int,
) -> tuple[str, str]:
    """POST to the queue; return (status_url, response_url) from the response body.

    fal.ai returns canonical status/result URLs that omit the model variant
    path segment (e.g. /o3/standard/…) — using those directly avoids 405s.
    """
    payload = {
        "image_url": _image_to_data_uri(image_a),
        "end_image_url": _image_to_data_uri(image_b),
        "prompt": prompt,
        "duration": str(duration),
        "generate_audio": False,
    }
    resp = requests.post(
        SUBMIT_URL,
        headers=_auth_headers(fal_key),
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    request_id = resp.json()["request_id"]
    # Construct canonical URLs — the status_url/response_url in the response
    # body use the full model variant path which returns 405 on GET.
    return f"{_STATUS_BASE}/{request_id}/status", f"{_STATUS_BASE}/{request_id}"


def _poll_until_done(status_url: str, fal_key: str) -> None:
    """Block until the queue reports COMPLETED or raises on error/timeout.

    fal.ai returns 405 with a valid JSON body for terminal states (COMPLETED,
    FAILED, CANCELLED, ALREADY_COMPLETED) — do not raise_for_status() here.
    """
    headers = {"Authorization": f"Key {fal_key}"}
    for wait in _POLL_INTERVALS_S:
        time.sleep(wait)
        resp = requests.get(status_url, headers=headers, timeout=30)
        data = resp.json()
        status = data.get("status", "")
        if status in ("COMPLETED", "ALREADY_COMPLETED"):
            return
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"fal.ai generation {status}: status_url={status_url}")
        if resp.status_code >= 400 and not status:
            resp.raise_for_status()
    raise TimeoutError(f"fal.ai generation timed out after {sum(_POLL_INTERVALS_S)}s")


def _fetch_result_url(response_url: str, fal_key: str) -> str:
    """After COMPLETED, fetch the mp4 URL from the result endpoint."""
    headers = {"Authorization": f"Key {fal_key}"}
    resp = requests.get(response_url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()["video"]["url"]


def _download(mp4_url: str) -> bytes:
    resp = requests.get(mp4_url, timeout=300)
    resp.raise_for_status()
    return resp.content


def generate_pair(
    image_a: Path,
    image_b: Path,
    prompt: str,
    fal_key: str,
    duration: int = 5,
) -> bytes:
    """Generate one first-last-frame interpolation video.

    Args:
        image_a: start frame path
        image_b: end frame path
        prompt: text describing the motion between frames
        fal_key: fal.ai API key (no `Key ` prefix)
        duration: video duration in seconds (fal.ai enum 3-15; default 5)

    Returns:
        Raw mp4 bytes. Caller writes to disk.

    Raises:
        requests.HTTPError on any 4xx/5xx at submit/poll/download
        RuntimeError if fal.ai reports FAILED/CANCELLED
        TimeoutError if polling exhausts without completion
    """
    status_url, response_url = _submit(image_a, image_b, prompt, fal_key, duration)
    _poll_until_done(status_url, fal_key)
    mp4_url = _fetch_result_url(response_url, fal_key)
    return _download(mp4_url)
