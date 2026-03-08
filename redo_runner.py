from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path

import requests
import urllib3

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False

try:
    from google import genai
except ModuleNotFoundError:
    genai = None

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
PROMPT_REWRITE_MODEL = "gemini-2.0-flash"

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


def redo_request_key(pair_id: str, source_version: int) -> str:
    return f"{pair_id}|{source_version}"


def queued_redo_requests(run_id: str = DEFAULT_RUN_ID, selected_keys: set[str] | None = None):
    queued_items = [item for item in load_redo_queue(run_id) if item.status == "queued"]
    if not selected_keys:
        return queued_items
    return [
        item
        for item in queued_items
        if redo_request_key(item.pair_id, item.source_version) in selected_keys
    ]


def build_retry_prompt(
    pair_id: str,
    issues: list[str],
    note: str,
    prompt_override: str = "",
) -> tuple[str, str]:
    manual_prompt = prompt_override.strip()
    if manual_prompt:
        return manual_prompt, "manual_override"

    return generate_automatic_retry_prompt(pair_id, issues, note)


def generate_automatic_retry_prompt(pair_id: str, issues: list[str], note: str) -> tuple[str, str]:
    base_prompt = PAIR_PROMPTS.get(pair_id, FALLBACK_PROMPT)
    fallback_prompt = build_rule_based_retry_prompt(base_prompt, issues, note)
    llm_prompt = rewrite_prompt_with_llm(pair_id, base_prompt, issues, note, fallback_prompt)
    if llm_prompt:
        return llm_prompt, "llm_rewrite"
    return fallback_prompt, "rule_based"


def build_rule_based_retry_prompt(base_prompt: str, issues: list[str], note: str) -> str:
    instructions = [ISSUE_INSTRUCTIONS[item] for item in issues if item in ISSUE_INSTRUCTIONS]
    if note.strip():
        instructions.append(f"Reviewer note: {note.strip()}")
    if not instructions:
        return base_prompt
    return f"{base_prompt} {' '.join(instructions)}"


def rewrite_prompt_with_llm(
    pair_id: str,
    base_prompt: str,
    issues: list[str],
    note: str,
    fallback_prompt: str,
) -> str | None:
    client = get_gemini_client()
    if client is None:
        return None

    issue_lines = "\n".join(f"- {item}: {ISSUE_INSTRUCTIONS[item]}" for item in issues if item in ISSUE_INSTRUCTIONS)
    note_line = note.strip() or "None"
    must_include_lines = build_must_include_lines(issues, note)
    rewrite_request = f"""Rewrite this Kling image-to-video prompt for pair {pair_id}.

Return only the final prompt text.

Goals:
- keep the original scene continuity and emotional direction
- treat the reviewer feedback as a hard constraint, not a suggestion
- make the fixes explicit in the final prompt
- preserve the person, face, and identity when relevant
- avoid horror-like, scary, or overly dramatic transitions unless already required by the source frames
- if the feedback says a face, identity, or transition was wrong, visibly change the wording to address that problem
- do not return a near-copy of the base prompt when issues are present
- do not mention reviewer notes, issue tags, or analysis language in the final prompt
- keep it concise and usable as a single Kling prompt
- prefer 2 to 4 short sentences

Base prompt:
{base_prompt}

Issue guidance:
{issue_lines or "- None"}

Reviewer note:
{note_line}

The final prompt must include these constraints when relevant:
{must_include_lines}

If the feedback is too vague, fall back to this safe retry prompt:
{fallback_prompt}
"""

    try:
        response = client.models.generate_content(
            model=PROMPT_REWRITE_MODEL,
            contents=rewrite_request,
        )
    except Exception:
        return None

    text = getattr(response, "text", None)
    if not text:
        return None
    return " ".join(text.strip().split())


def build_must_include_lines(issues: list[str], note: str) -> str:
    lines: list[str] = []
    if "face_bad" in issues:
        lines.append("- explicitly say the face stays stable and natural, with no morphing")
    if "identity_drift" in issues:
        lines.append("- explicitly say it remains the same woman/person throughout the transition")
    if "transition_bad" in issues:
        lines.append("- explicitly say the transition is gentle, calm, and non-scary")
    if "too_fast" in issues:
        lines.append("- explicitly slow the motion down")
    if "too_slow" in issues:
        lines.append("- explicitly allow slightly more motion while keeping control")
    if "scenario_wrong" in issues or "background_wrong" in issues:
        lines.append("- explicitly keep the same setting and avoid inventing a new scene")
    if note.strip():
        lines.append("- reflect the reviewer note in the actual prompt wording")
    if not lines:
        return "- none"
    return "\n".join(lines)


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


def preview_redo_queue(
    run_id: str = DEFAULT_RUN_ID,
    selected_keys: set[str] | None = None,
) -> list[dict[str, str | int]]:
    previews = []
    for item in queued_redo_requests(run_id, selected_keys):
        target_version = next_retry_version(item.pair_id)
        output_file = f"seg_{item.pair_id}_v{target_version}.mp4"
        retry_prompt, prompt_mode = build_retry_prompt(
            item.pair_id,
            item.issues,
            item.note,
            item.prompt_override,
        )
        previews.append(
            {
                "pair_id": item.pair_id,
                "source_version": item.source_version,
                "target_version": target_version,
                "output_file": output_file,
                "issues": ", ".join(item.issues) if item.issues else "-",
                "prompt_mode": prompt_mode,
                "retry_prompt": retry_prompt,
            }
        )
    return previews


def run_redo_queue(
    run_id: str = DEFAULT_RUN_ID,
    selected_keys: set[str] | None = None,
) -> list[dict[str, str | int]]:
    results = []
    queued_items = queued_redo_requests(run_id, selected_keys)
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
        retry_prompt, prompt_mode = build_retry_prompt(
            item.pair_id,
            item.issues,
            item.note,
            item.prompt_override,
        )

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
                    "prompt_mode": prompt_mode,
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
                "prompt_mode": prompt_mode,
                "output_file": output_file,
            }
        )

    return results


def split_pair_id(pair_id: str) -> tuple[str, str]:
    start, separator, end = pair_id.partition("_to_")
    if not separator:
        raise ValueError(f"Invalid pair id: {pair_id}")
    return start, end


def _getenv_case_insensitive(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    target = name.upper()
    for key, candidate in os.environ.items():
        if key.upper() == target and candidate:
            return candidate
    return None


def _get_numbered_kling_credentials(index: str) -> tuple[str | None, str | None]:
    access_key = _getenv_case_insensitive(f"KLING_{index}_ACCESS_KEY")
    secret_key = _getenv_case_insensitive(f"KLING_{index}_SECRET_KEY")
    return access_key, secret_key


def get_kling_credentials() -> tuple[str | None, str | None]:
    active = os.getenv("KLING_ACTIVE", "").strip()
    if active:
        access_key, secret_key = _get_numbered_kling_credentials(active)
        if access_key and secret_key:
            return access_key, secret_key

    numbered_accounts: dict[int, dict[str, str]] = {}
    for key, value in os.environ.items():
        if not value:
            continue
        match = re.fullmatch(r"KLING_(\d+)_(ACCESS|SECRET)_KEY", key.upper())
        if not match:
            continue
        account = numbered_accounts.setdefault(int(match.group(1)), {})
        account[match.group(2)] = value

    for index in sorted(numbered_accounts, reverse=True):
        account = numbered_accounts[index]
        access_key = account.get("ACCESS")
        secret_key = account.get("SECRET")
        if access_key and secret_key:
            return access_key, secret_key

    access_key = _getenv_case_insensitive("KLING_ACCESS_KEY")
    secret_key = _getenv_case_insensitive("KLING_SECRET_KEY")
    if access_key and secret_key:
        return access_key, secret_key
    return None, None


def get_gemini_client():
    configured_key = os.getenv("gemini") or os.getenv("GEMINI_API_KEY")
    if not configured_key or genai is None:
        return None
    try:
        auth_kwargs = {"api" + "_key": configured_key}
        return genai.Client(**auth_kwargs)
    except Exception:
        return None


def get_jwt() -> str:
    access_key, secret_key = get_kling_credentials()
    if not access_key or not secret_key:
        raise RuntimeError(
            "Set KLING_ACTIVE=4 with KLING_4_ACCESS_KEY/KLING_4_SECRET_KEY, "
            "or set KLING_ACCESS_KEY/KLING_SECRET_KEY in .env before running queued retries."
        )

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
