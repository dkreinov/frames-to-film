from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

import requests
import urllib3

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False

from image_pair_prompts import FALLBACK_PROMPT, PAIR_PROMPTS
from review_store import DEFAULT_RUN_ID, VIDEOS_DIR, frame_image_path, load_redo_queue, save_redo_result


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR.parent / ".env")
load_dotenv(SCRIPT_DIR / ".env")

API_BASE = "https://api.klingai.com"
MODEL = "kling-v3"
DURATION = "8"
POLL_INTERVALS = [15, 20, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30]

ISSUE_INSTRUCTIONS = {
    "face_bad": "Keep the same face and facial structure throughout the shot. Avoid facial distortion or morphing.",
    "identity_drift": "Preserve the same person from start to end with stable identity, age, and features.",
    "hands_body_bad": "Keep anatomy natural and stable. Avoid broken hands, warped limbs, or body distortion.",
    "transition_bad": "Use a gentle, emotionally natural transition with restrained motion and no sudden horror-like beats.",
    "scenario_wrong": "Do not invent a new scene. Stay anchored to the two provided frames and their implied setting.",
    "background_wrong": "Keep the environment consistent with the source frames. Do not replace the background with a different location.",
    "style_mismatch": "Preserve the original photographic style, lighting continuity, and period feel.",
    "too_fast": "Slow the movement down. Favor subtle motion over dramatic action.",
    "too_slow": "Add slightly more motion, but keep it controlled and realistic.",
    "artifacts": "Avoid flicker, warping, ghosting, or visible image-generation artifacts.",
    "emotion_wrong": "Keep the emotional tone gentle and true to the source frames.",
    "prompt_ignored": "Follow the transition exactly. Prioritize frame continuity over creative invention.",
}


def queued_redo_requests(run_id: str = DEFAULT_RUN_ID):
    return [item for item in load_redo_queue(run_id) if item.status == "queued"]


def build_retry_prompt(pair_id: str, issues: list[str], note: str) -> str:
    base_prompt = PAIR_PROMPTS.get(pair_id, FALLBACK_PROMPT)
    instructions = [ISSUE_INSTRUCTIONS[item] for item in issues if item in ISSUE_INSTRUCTIONS]
    if note.strip():
        instructions.append(f"Reviewer note: {note.strip()}")
    if not instructions:
        return base_prompt
    return f"{base_prompt} {' '.join(instructions)}"


def next_retry_version(pair_id: str, videos_dir: Path = VIDEOS_DIR) -> int:
    highest_version = 1
    for path in videos_dir.glob(f"seg_{pair_id}*.mp4"):
        name = path.stem
        if name == f"seg_{pair_id}":
            highest_version = max(highest_version, 1)
            continue
        suffix = name.removeprefix(f"seg_{pair_id}_v")
        if suffix.isdigit():
            highest_version = max(highest_version, int(suffix))
    return highest_version + 1


def preview_redo_queue(run_id: str = DEFAULT_RUN_ID) -> list[dict[str, str | int]]:
    previews = []
    for item in queued_redo_requests(run_id):
        target_version = next_retry_version(item.pair_id)
        output_file = f"seg_{item.pair_id}_v{target_version}.mp4"
        previews.append(
            {
                "pair_id": item.pair_id,
                "source_version": item.source_version,
                "target_version": target_version,
                "output_file": output_file,
                "issues": ", ".join(item.issues) if item.issues else "-",
                "retry_prompt": build_retry_prompt(item.pair_id, item.issues, item.note),
            }
        )
    return previews


def run_redo_queue(run_id: str = DEFAULT_RUN_ID) -> list[dict[str, str | int]]:
    results = []
    queued_items = queued_redo_requests(run_id)
    if not queued_items:
        return results

    token = get_jwt()
    token_time = time.time()
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    for item in queued_items:
        if time.time() - token_time > 1500:
            token = get_jwt()
            token_time = time.time()

        start_frame, end_frame = split_pair_id(item.pair_id)
        start_path = frame_image_path(start_frame)
        end_path = frame_image_path(end_frame)
        target_version = next_retry_version(item.pair_id)
        output_file = f"seg_{item.pair_id}_v{target_version}.mp4"
        output_path = VIDEOS_DIR / output_file
        retry_prompt = build_retry_prompt(item.pair_id, item.issues, item.note)

        try:
            task_id, error = submit_video(token, start_path, end_path, retry_prompt)
            if not task_id:
                raise RuntimeError(error or "submit failed")

            video_url = poll_task(token, task_id)
            if not video_url:
                raise RuntimeError("poll failed")

            download_video(video_url, output_path)
        except Exception as error:
            save_redo_result(
                item.pair_id,
                item.source_version,
                "failed",
                run_id,
                error=str(error),
                retry_prompt=retry_prompt,
            )
            results.append(
                {
                    "pair_id": item.pair_id,
                    "source_version": item.source_version,
                    "target_version": target_version,
                    "status": "failed",
                    "error": str(error),
                }
            )
            continue

        save_redo_result(
            item.pair_id,
            item.source_version,
            "waiting_review",
            run_id,
            target_version=target_version,
            output_file=output_file,
            retry_prompt=retry_prompt,
        )
        results.append(
            {
                "pair_id": item.pair_id,
                "source_version": item.source_version,
                "target_version": target_version,
                "status": "waiting_review",
                "output_file": output_file,
            }
        )

    return results


def split_pair_id(pair_id: str) -> tuple[str, str]:
    start, separator, end = pair_id.partition("_to_")
    if not separator:
        raise ValueError(f"Invalid pair id: {pair_id}")
    return start, end


def get_kling_credentials() -> tuple[str | None, str | None]:
    active = os.getenv("KLING_ACTIVE", "").strip()
    if active:
        access_key = os.getenv(f"KLING_{active}_ACCESS_KEY")
        secret_key = os.getenv(f"KLING_{active}_SECRET_KEY")
        if access_key and secret_key:
            return access_key, secret_key

    access_key = os.getenv("KLING_ACCESS_KEY")
    secret_key = os.getenv("KLING_SECRET_KEY")
    if access_key and secret_key:
        return access_key, secret_key
    return None, None


def get_jwt() -> str:
    access_key, secret_key = get_kling_credentials()
    if not access_key or not secret_key:
        raise RuntimeError("Set Kling credentials in .env before running queued retries.")

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64url(
        json.dumps(
            {
                "iss": access_key,
                "exp": int(time.time()) + 1800,
                "nbf": int(time.time()) - 5,
            }
        ).encode()
    )
    signature = b64url(hmac.new(secret_key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def img_to_base64(path: Path) -> str:
    with path.open("rb") as handle:
        return base64.b64encode(handle.read()).decode()


def submit_video(token: str, start_path: Path, end_path: Path, prompt: str) -> tuple[str | None, str | None]:
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {
        "model_name": MODEL,
        "image": img_to_base64(start_path),
        "image_tail": img_to_base64(end_path),
        "prompt": prompt,
        "duration": DURATION,
        "cfg_scale": 0.5,
        "enable_audio": False,
    }
    try:
        response = requests.post(
            f"{API_BASE}/v1/videos/image2video",
            headers=headers,
            json=payload,
            verify=False,
            timeout=180,
        )
        data = response.json()
    except Exception as error:
        return None, str(error)
    if data.get("code") != 0:
        return None, data.get("message", "unknown error")
    return data["data"]["task_id"], None


def poll_task(token: str, task_id: str) -> str | None:
    headers = {"Authorization": f"Bearer {token}"}
    for wait in POLL_INTERVALS:
        time.sleep(wait)
        try:
            response = requests.get(
                f"{API_BASE}/v1/videos/image2video/{task_id}",
                headers=headers,
                verify=False,
                timeout=30,
            )
            data = response.json()
        except Exception:
            continue

        if data.get("code") != 0:
            continue

        task = data.get("data", {})
        status = task.get("task_status", "unknown")
        if status == "succeed":
            videos = task.get("task_result", {}).get("videos", [])
            return videos[0].get("url") if videos else None
        if status == "failed":
            return None

    return None


def download_video(url: str, output_path: Path) -> None:
    response = requests.get(url, verify=False, timeout=120)
    response.raise_for_status()
    output_path.write_bytes(response.content)
