#!/usr/bin/env python3
"""Generate Kling AI videos from consecutive numbered image pairs (start+end frame)."""
import os
import sys
import time
import hmac
import hashlib
import base64
import json
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, '.env'))

IMG_DIR = os.path.join(SCRIPT_DIR, "kling_test")
VID_DIR = os.path.join(IMG_DIR, "videos")

API_BASE = "https://api.klingai.com"
MODEL = "kling-v3"
DURATION = "5"
POLL_INTERVALS = [10, 15, 20, 30, 30, 30, 30, 30, 30, 30, 30, 30]  # ~5 min total

TRANSITION_PROMPTS = {
    (1, 2): (
        "Slow cinematic push-in. The snowy winter scene gradually dissolves through "
        "soft light into a warm close-up of a smiling baby. Gentle camera drift. "
        "Vintage sepia film grain. Nostalgic, tender family memory. "
        "Smooth, dreamlike transition."
    ),
    (2, 3): (
        "Gentle camera pull-back revealing a cozy living room. The baby's smile "
        "softly transitions into a little girl sitting on a plaid couch holding "
        "her doll. Slow, steady movement. Black and white vintage film look. "
        "Warm, loving atmosphere. Seamless natural flow."
    ),
}

FALLBACK_PROMPT = (
    "Smooth cinematic transition between the two frames. Gentle camera movement. "
    "Nostalgic vintage film look. Warm, natural, dreamlike flow."
)


def get_jwt():
    ak = os.getenv('KLING_ACCESS_KEY')
    sk = os.getenv('KLING_SECRET_KEY')
    if not ak or not sk:
        print("ERROR: KLING_ACCESS_KEY/KLING_SECRET_KEY not found in .env", file=sys.stderr)
        sys.exit(1)

    def b64url(data):
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64url(json.dumps({
        "iss": ak,
        "exp": int(time.time()) + 1800,
        "nbf": int(time.time()) - 5,
    }).encode())
    sig = b64url(hmac.new(sk.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def img_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def submit_video(token, start_path, end_path, prompt):
    url = f"{API_BASE}/v1/videos/image2video"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "model_name": MODEL,
        "image": img_to_base64(start_path),
        "image_tail": img_to_base64(end_path),
        "prompt": prompt,
        "duration": DURATION,
        "cfg_scale": 0.5,
        "enable_audio": False,
    }

    resp = requests.post(url, headers=headers, json=payload, verify=False, timeout=120)
    data = resp.json()

    if data.get("code") != 0:
        print(f"  API error: {data}")
        return None

    task_id = data["data"]["task_id"]
    print(f"  Task submitted: {task_id}")
    return task_id


def poll_task(token, task_id):
    url = f"{API_BASE}/v1/videos/image2video/{task_id}"
    headers = {"Authorization": f"Bearer {token}"}

    for i, wait in enumerate(POLL_INTERVALS):
        time.sleep(wait)
        resp = requests.get(url, headers=headers, verify=False, timeout=30)
        data = resp.json()

        if data.get("code") != 0:
            print(f"  Poll error: {data}")
            continue

        task = data.get("data", {})
        status = task.get("task_status", "unknown")
        print(f"  [{i+1}/{len(POLL_INTERVALS)}] status={status}")

        if status == "succeed":
            videos = task.get("task_result", {}).get("videos", [])
            if videos:
                return videos[0].get("url")
            return None
        elif status == "failed":
            print(f"  Task failed: {task.get('task_status_msg', 'unknown')}")
            return None

    print("  Timeout waiting for task")
    return None


def download_video(url, out_path):
    resp = requests.get(url, verify=False, timeout=120)
    with open(out_path, "wb") as f:
        f.write(resp.content)
    size_mb = len(resp.content) / (1024 * 1024)
    print(f"  Downloaded: {out_path} ({size_mb:.1f} MB)")


def get_image_pairs():
    files = sorted(
        f for f in os.listdir(IMG_DIR)
        if f.lower().endswith(('.jpg', '.jpeg', '.png')) and f.split('.')[0].isdigit()
    )
    nums = sorted(int(f.split('.')[0]) for f in files)
    pairs = []
    for i in range(len(nums) - 1):
        a, b = nums[i], nums[i + 1]
        ext_a = next(f for f in files if f.startswith(f"{a}."))
        ext_b = next(f for f in files if f.startswith(f"{b}."))
        pairs.append((a, b, os.path.join(IMG_DIR, ext_a), os.path.join(IMG_DIR, ext_b)))
    return pairs


def main():
    os.makedirs(VID_DIR, exist_ok=True)
    token = get_jwt()
    pairs = get_image_pairs()

    print(f"Generating {len(pairs)} video segments")
    print(f"Model: {MODEL} | Duration: {DURATION}s")
    print("-" * 60)

    for a, b, path_a, path_b in pairs:
        prompt = TRANSITION_PROMPTS.get((a, b), FALLBACK_PROMPT)
        out_path = os.path.join(VID_DIR, f"segment_{a}_{b}.mp4")

        print(f"\n[{a} -> {b}]")
        print(f"  Start: {os.path.basename(path_a)}")
        print(f"  End:   {os.path.basename(path_b)}")

        task_id = submit_video(token, path_a, path_b, prompt)
        if not task_id:
            print(f"  FAILED to submit")
            continue

        video_url = poll_task(token, task_id)
        if not video_url:
            print(f"  FAILED to get video")
            continue

        download_video(video_url, out_path)

    print("\n" + "-" * 60)
    vids = [f for f in os.listdir(VID_DIR) if f.endswith('.mp4')]
    print(f"Done. {len(vids)} videos in {VID_DIR}")


if __name__ == "__main__":
    main()
