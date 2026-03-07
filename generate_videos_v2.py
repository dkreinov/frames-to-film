#!/usr/bin/env python3
"""Generate Kling AI video variants with different prompt styles (8s, no audio)."""
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
DURATION = "8"
POLL_INTERVALS = [15, 20, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30]

VARIANTS = {
    (1, 2): [
        ("cinematic", (
            "Slow dolly push-in, 35mm film look. Soft golden light dissolves "
            "the winter scene into a warm close-up. Gentle handheld drift. "
            "Sepia tone, film grain. Tender, nostalgic."
        )),
        ("minimal", "Gentle push-in, cinematic continuity, soft lighting carryover, vintage warmth."),
        ("promptless", ""),
    ],
    (2, 3): [
        ("cinematic", (
            "Slow tracking shot pulling back. The intimate close-up gradually "
            "reveals a cozy living room. Steadicam movement. Vintage black and "
            "white film grain. Warm soft focus. Nostalgic family memory."
        )),
        ("minimal", "Gentle pull-back, cinematic continuity, soft focus transition, warm vintage feel."),
        ("promptless", ""),
    ],
}


def get_jwt():
    ak = os.getenv('KLING_ACCESS_KEY')
    sk = os.getenv('KLING_SECRET_KEY')
    if not ak or not sk:
        sys.exit("ERROR: KLING_ACCESS_KEY/KLING_SECRET_KEY not in .env")

    def b64url(data):
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64url(json.dumps({
        "iss": ak, "exp": int(time.time()) + 1800, "nbf": int(time.time()) - 5,
    }).encode())
    sig = b64url(hmac.new(sk.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def img_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def submit_video(token, start_path, end_path, prompt):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {
        "model_name": MODEL,
        "image": img_to_base64(start_path),
        "image_tail": img_to_base64(end_path),
        "duration": DURATION,
        "cfg_scale": 0.5,
        "enable_audio": False,
    }
    if prompt:
        payload["prompt"] = prompt

    resp = requests.post(f"{API_BASE}/v1/videos/image2video",
                         headers=headers, json=payload, verify=False, timeout=120)
    data = resp.json()
    if data.get("code") != 0:
        print(f"  API error: {data.get('message')}")
        return None
    task_id = data["data"]["task_id"]
    print(f"  Task: {task_id}")
    return task_id


def poll_task(token, task_id):
    headers = {"Authorization": f"Bearer {token}"}
    for i, wait in enumerate(POLL_INTERVALS):
        time.sleep(wait)
        resp = requests.get(f"{API_BASE}/v1/videos/image2video/{task_id}",
                            headers=headers, verify=False, timeout=30)
        data = resp.json()
        if data.get("code") != 0:
            continue
        task = data.get("data", {})
        status = task.get("task_status", "unknown")
        print(f"  [{i+1}] {status}", end="", flush=True)
        if status == "succeed":
            videos = task.get("task_result", {}).get("videos", [])
            url = videos[0].get("url") if videos else None
            print()
            return url
        elif status == "failed":
            print(f" -- {task.get('task_status_msg', '')}")
            return None
    print("\n  Timeout")
    return None


def download_video(url, out_path):
    resp = requests.get(url, verify=False, timeout=120)
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"  -> {out_path} ({len(resp.content)/1024/1024:.1f} MB)")


def main():
    os.makedirs(VID_DIR, exist_ok=True)
    token = get_jwt()

    pairs = [(1, 2), (2, 3)]
    total = sum(len(VARIANTS[p]) for p in pairs)
    print(f"Generating {total} video variants ({DURATION}s each, no audio)")
    print("=" * 60)

    for a, b in pairs:
        start_path = os.path.join(IMG_DIR, f"{a}.jpg")
        end_path = os.path.join(IMG_DIR, f"{b}.jpg")

        for style, prompt in VARIANTS[(a, b)]:
            out_path = os.path.join(VID_DIR, f"segment_{a}_{b}_{style}.mp4")
            label = f"[{a}->{b} {style}]"
            prompt_preview = prompt[:60] + "..." if len(prompt) > 60 else (prompt or "(no prompt)")

            print(f"\n{label} {prompt_preview}")
            task_id = submit_video(token, start_path, end_path, prompt)
            if not task_id:
                continue
            video_url = poll_task(token, task_id)
            if not video_url:
                continue
            download_video(video_url, out_path)

    vids = [f for f in os.listdir(VID_DIR) if f.endswith('.mp4')]
    print(f"\n{'=' * 60}\nDone. {len(vids)} total videos in {VID_DIR}")


if __name__ == "__main__":
    main()
