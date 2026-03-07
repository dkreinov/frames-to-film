#!/usr/bin/env python3
"""Outpaint all numbered 4:3 images to 16:9 using Gemini Pro for Kling AI video generation."""
import os
import re
import time
from io import BytesIO
from dotenv import load_dotenv
from PIL import Image
from google import genai
from google.genai import types

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outpainted")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kling_test")
TARGET_W, TARGET_H = 5376, 3024  # 16:9
IMAGE_MODEL = "gemini-3-pro-image-preview"
API_DELAY = 10

PROMPT = (
    "Extend this photograph to 16:9 widescreen landscape aspect ratio by widening it horizontally. "
    "Every person must remain exactly as they are -- do not alter any person, face, expression, body, or clothing at all. "
    "Only extend the background on both sides naturally. Match the existing lighting, colors, textures, "
    "and photographic style exactly. No seams, no visible transitions."
)


def sort_key(filename):
    """Sort: 1, 2, ..., 33, 33_b, 34, 35, 35_b, 36, ..., 41"""
    base = filename.split('.')[0]
    match = re.match(r'^(\d+)(_([a-z]))?$', base)
    if match:
        num = int(match.group(1))
        suffix = match.group(3) or ''
        return (num, suffix)
    return (9999, base)


def get_client():
    api_key = os.getenv('gemini')
    if not api_key:
        raise RuntimeError("No 'gemini' key found in .env")
    return genai.Client(api_key=api_key)


def outpaint(client, img, prompt):
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    pil_for_api = Image.open(buf)

    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[prompt, pil_for_api],
        config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            result = Image.open(BytesIO(part.inline_data.data))
            if result.mode != 'RGB':
                result = result.convert('RGB')
            return result
    return None


def upscale_to_target(img):
    w, h = img.size
    if w >= TARGET_W and h >= TARGET_H:
        return img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    scale = max(TARGET_W / w, TARGET_H / h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - TARGET_W) // 2
    top = (new_h - TARGET_H) // 2
    return img.crop((left, top, left + TARGET_W, top + TARGET_H))


def get_numbered_images():
    files = [
        f for f in os.listdir(SRC_DIR)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        and re.match(r'^\d+(_[a-z])?\.', f)
    ]
    return sorted(files, key=sort_key)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    client = get_client()

    all_files = get_numbered_images()
    already_done = set(os.listdir(OUT_DIR))
    todo = [f for f in all_files if f not in already_done]

    print(f"Total numbered images: {len(all_files)}")
    print(f"Already done: {len(all_files) - len(todo)}")
    print(f"To process: {len(todo)}")
    print("-" * 60)

    for i, filename in enumerate(todo):
        src = os.path.join(SRC_DIR, filename)
        out = os.path.join(OUT_DIR, filename)

        img = Image.open(src)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        print(f"[{i+1}/{len(todo)}] {filename}: {img.size}", end="", flush=True)

        try:
            result = outpaint(client, img, PROMPT)
        except Exception as e:
            print(f" ERROR: {e}")
            time.sleep(API_DELAY)
            continue

        if result is None:
            print(" FAILED (no image)")
            time.sleep(API_DELAY)
            continue

        result = upscale_to_target(result)
        result.save(out, "JPEG", quality=95)
        print(f" -> {result.size} OK")
        time.sleep(API_DELAY)

    done = len([f for f in os.listdir(OUT_DIR) if f.lower().endswith('.jpg')])
    print(f"\nDone. {done} images in {OUT_DIR}")


if __name__ == "__main__":
    main()
