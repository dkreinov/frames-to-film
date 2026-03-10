#!/usr/bin/env python3
"""Generate Kling AI cinematic videos for ALL consecutive numbered image pairs."""
import os
import sys
import re
import time
import hmac
import hashlib
import base64
import json
import requests
import urllib3
from dotenv import load_dotenv
from image_pair_prompts import PAIR_PROMPTS, FALLBACK_PROMPT

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Load root .env first (optional), then olga_movie .env (overrides)
load_dotenv(os.path.join(SCRIPT_DIR, '..', '.env'))
load_dotenv(os.path.join(SCRIPT_DIR, '.env'))

IMG_DIR = os.path.join(SCRIPT_DIR, "kling_test")
VID_DIR = os.path.join(IMG_DIR, "videos")
STATUS_PATH = os.path.join(VID_DIR, "status.json")

API_BASE = "https://api.klingai.com"
MODEL = "kling-v3"
DURATION = "8"
POLL_INTERVALS = [15, 20, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30]

SKIP_PAIRS = {"1_to_2", "2_to_3"}


def sort_key(filename):
    base = filename.split('.')[0]
    match = re.match(r'^(\d+)(_([a-z]))?$', base)
    if match:
        return (int(match.group(1)), match.group(3) or '')
    return (9999, base)


def reload_kling_env():
    load_dotenv(os.path.join(SCRIPT_DIR, '..', '.env'), override=True)
    load_dotenv(os.path.join(SCRIPT_DIR, '.env'), override=True)


def get_kling_credentials():
    """Read active Kling keys, tolerating case variants and numbered account rotation."""
    reload_kling_env()

    def getenv_case_insensitive(name):
        value = os.getenv(name)
        if value:
            return value

        target = name.upper()
        for key, candidate in os.environ.items():
            if key.upper() == target and candidate:
                return candidate
        return None

    def get_numbered_pair(index):
        return (
            getenv_case_insensitive(f'KLING_{index}_ACCESS_KEY'),
            getenv_case_insensitive(f'KLING_{index}_SECRET_KEY'),
        )

    active = os.getenv('KLING_ACTIVE', '').strip()
    if active:
        ak, sk = get_numbered_pair(active)
        if ak and sk:
            return ak, sk

    numbered_accounts = {}
    for key, value in os.environ.items():
        if not value:
            continue
        match = re.fullmatch(r'KLING_(\d+)_(ACCESS|SECRET)_KEY', key.upper())
        if not match:
            continue
        account = numbered_accounts.setdefault(int(match.group(1)), {})
        account[match.group(2)] = value

    for index in sorted(numbered_accounts, reverse=True):
        account = numbered_accounts[index]
        ak = account.get('ACCESS')
        sk = account.get('SECRET')
        if ak and sk:
            return ak, sk

    ak = getenv_case_insensitive('KLING_ACCESS_KEY')
    sk = getenv_case_insensitive('KLING_SECRET_KEY')
    return (ak, sk) if (ak and sk) else (None, None)


def get_jwt():
    ak, sk = get_kling_credentials()
    if not ak or not sk:
        sys.exit(
            "ERROR: Set KLING_ACTIVE=4 with KLING_4_ACCESS_KEY/KLING_4_SECRET_KEY, "
            "or set KLING_ACCESS_KEY/KLING_SECRET_KEY in .env."
        )

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
        "prompt": prompt,
        "duration": DURATION,
        "cfg_scale": 0.5,
        "enable_audio": False,
    }

    resp = requests.post(f"{API_BASE}/v1/videos/image2video",
                         headers=headers, json=payload, verify=False, timeout=180)
    data = resp.json()
    if data.get("code") != 0:
        return None, data.get("message", "unknown error")
    return data["data"]["task_id"], None


def poll_task(token, task_id):
    headers = {"Authorization": f"Bearer {token}"}
    for i, wait in enumerate(POLL_INTERVALS):
        time.sleep(wait)
        try:
            resp = requests.get(f"{API_BASE}/v1/videos/image2video/{task_id}",
                                headers=headers, verify=False, timeout=30)
            data = resp.json()
        except Exception:
            continue

        if data.get("code") != 0:
            continue

        task = data.get("data", {})
        status = task.get("task_status", "unknown")
        print(f".", end="", flush=True)

        if status == "succeed":
            videos = task.get("task_result", {}).get("videos", [])
            return videos[0].get("url") if videos else None
        elif status == "failed":
            print(f" FAILED:{task.get('task_status_msg','')}", end="")
            return None

    print(" TIMEOUT", end="")
    return None


def download_video(url, out_path):
    resp = requests.get(url, verify=False, timeout=120)
    with open(out_path, "wb") as f:
        f.write(resp.content)
    return len(resp.content) / (1024 * 1024)


def get_image_sequence():
    files = [
        f for f in os.listdir(IMG_DIR)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        and re.match(r'^\d+(_[a-z])?\.', f)
    ]
    return sorted(files, key=sort_key)


def build_pairs_from_sequence(files):
    pairs = []
    for i in range(len(files) - 1):
        a_name = files[i].split('.')[0]
        b_name = files[i + 1].split('.')[0]
        key = f"{a_name}_to_{b_name}"
        pairs.append((files[i], files[i + 1], key))
    return pairs


def load_status():
    if os.path.exists(STATUS_PATH):
        with open(STATUS_PATH) as f:
            return json.load(f)
    return {}


def save_status(status):
    with open(STATUS_PATH, 'w') as f:
        json.dump(status, f, indent=2)


def generate_pairs_for_sequence(
    files,
    image_dir=None,
    video_dir=None,
    status_path=None,
    selected_keys=None,
):
    image_dir = image_dir or IMG_DIR
    video_dir = video_dir or VID_DIR
    status_path = status_path or STATUS_PATH
    os.makedirs(video_dir, exist_ok=True)

    def load_status_for_path():
        if os.path.exists(status_path):
            with open(status_path) as f:
                return json.load(f)
        return {}

    def save_status_for_path(status):
        with open(status_path, 'w') as f:
            json.dump(status, f, indent=2)

    sequence_pairs = build_pairs_from_sequence(files)
    if selected_keys is not None:
        selected = set(selected_keys)
        sequence_pairs = [pair for pair in sequence_pairs if pair[2] in selected]

    status = load_status_for_path()
    token = get_jwt()
    token_time = time.time()
    results = []

    for f_a, f_b, key in sequence_pairs:
        if time.time() - token_time > 1500:
            token = get_jwt()
            token_time = time.time()

        a_name = f_a.split('.')[0]
        b_name = f_b.split('.')[0]
        out_path = os.path.join(video_dir, f"seg_{a_name}_to_{b_name}.mp4")
        path_a = os.path.join(image_dir, f_a)
        path_b = os.path.join(image_dir, f_b)
        prompt = PAIR_PROMPTS.get(key, FALLBACK_PROMPT)

        task_id, err = submit_video(token, path_a, path_b, prompt)
        if not task_id:
            status[key] = {"result": "submit_fail", "error": err}
            save_status_for_path(status)
            results.append({"pair_key": key, "result": "submit_fail", "error": err, "prompt": prompt})
            continue

        video_url = poll_task(token, task_id)
        if not video_url:
            status[key] = {"result": "poll_fail", "task_id": task_id}
            save_status_for_path(status)
            results.append({"pair_key": key, "result": "poll_fail", "task_id": task_id, "prompt": prompt})
            continue

        size_mb = download_video(video_url, out_path)
        status[key] = {
            "result": "ok",
            "task_id": task_id,
            "file": os.path.basename(out_path),
            "size_mb": round(size_mb, 1),
        }
        save_status_for_path(status)
        results.append(
            {
                "pair_key": key,
                "result": "ok",
                "task_id": task_id,
                "file": os.path.basename(out_path),
                "size_mb": round(size_mb, 1),
                "prompt": prompt,
            }
        )

    return results


def main():
    os.makedirs(VID_DIR, exist_ok=True)
    files = get_image_sequence()
    status = load_status()

    pairs = []
    for i in range(len(files) - 1):
        a_name = files[i].split('.')[0]
        b_name = files[i + 1].split('.')[0]
        key = f"{a_name}_to_{b_name}"
        if key in SKIP_PAIRS:
            continue
        if key not in status or status[key].get("result") != "ok":
            pairs.append((files[i], files[i + 1], key))

    print(f"Image sequence: {len(files)} images")
    print(f"Pairs to generate: {len(pairs)} (skipping {len(files)-1-len(pairs)} already done)")
    print(f"Model: {MODEL} | Duration: {DURATION}s | Audio: off")
    print("=" * 70)

    # JWT expires in 30 min, regenerate periodically
    token = get_jwt()
    token_time = time.time()

    for idx, (f_a, f_b, key) in enumerate(pairs):
        # Refresh token every 25 min
        if time.time() - token_time > 1500:
            token = get_jwt()
            token_time = time.time()

        a_name = f_a.split('.')[0]
        b_name = f_b.split('.')[0]
        out_path = os.path.join(VID_DIR, f"seg_{a_name}_to_{b_name}.mp4")

        path_a = os.path.join(IMG_DIR, f_a)
        path_b = os.path.join(IMG_DIR, f_b)

        prompt = PAIR_PROMPTS.get(key, FALLBACK_PROMPT)
        print(f"[{idx+1}/{len(pairs)}] {a_name} -> {b_name}", end=" ", flush=True)

        task_id, err = submit_video(token, path_a, path_b, prompt)
        if not task_id:
            print(f"SUBMIT FAIL: {err}")
            status[key] = {"result": "submit_fail", "error": err}
            save_status(status)
            continue

        print(f"task={task_id[:12]}.. polling", end="", flush=True)
        video_url = poll_task(token, task_id)

        if not video_url:
            print(f" NO VIDEO")
            status[key] = {"result": "poll_fail", "task_id": task_id}
            save_status(status)
            continue

        size_mb = download_video(video_url, out_path)
        print(f" OK ({size_mb:.1f}MB)")
        status[key] = {"result": "ok", "task_id": task_id, "file": os.path.basename(out_path), "size_mb": round(size_mb, 1)}
        save_status(status)

    ok = sum(1 for v in status.values() if v.get("result") == "ok")
    total = len(files) - 1
    print(f"\n{'=' * 70}")
    print(f"Done. {ok}/{total} segments complete.")


if __name__ == "__main__":
    main()
