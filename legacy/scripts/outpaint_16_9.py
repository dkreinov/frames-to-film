#!/usr/bin/env python3
"""Outpaint all numbered 4:3 images to 16:9 using Gemini Pro for Kling AI video generation."""
import os
import re
import threading
import time
from io import BytesIO
from dotenv import load_dotenv
from PIL import Image, ImageOps
from google import genai
from google.genai import types

from watermark_clean import clean_if_enabled

_RUN_LOCK = threading.Lock()

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outpainted")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kling_test")
TARGET_W, TARGET_H = 5376, 3024  # 16:9
IMAGE_MODEL = "gemini-3-pro-image-preview"
API_DELAY = 10
TARGET_ASPECT_RATIO = TARGET_W / TARGET_H

PROMPT = (
    "Extend this photograph to 16:9 widescreen landscape aspect ratio by widening it horizontally. "
    "Every person must remain exactly as they are -- do not alter any person, face, expression, body, or clothing at all. "
    "Only extend the background on both sides naturally. Match the existing lighting, colors, textures, "
    "and photographic style exactly. No seams, no visible transitions."
)

PORTRAIT_PROMPT = (
    "This is a portrait-oriented photograph that needs to become 16:9 by widening only left and right. "
    "Keep every person exactly unchanged, especially the same face, expression, hair, body, clothing, and pose. "
    "Do not morph, replace, restyle, or invent a different person. Preserve the existing center composition exactly as it is. "
    "Only extend the background on both sides naturally, matching the current lighting, colors, textures, and photographic realism. "
    "No seams, no visible transitions."
)

PRESERVE_PROMPT = (
    "This image is already an edited composition. Preserve the existing image exactly as it is. "
    "Expand only the left and right outer edges as needed to reach a 16:9 landscape frame. "
    "Do not change any person, face, expression, body, clothing, pose, or the existing central composition. "
    "Only continue the surrounding background naturally. Match the current lighting, colors, textures, and photographic realism. "
    "No seams, no visible transitions."
)

MINIMAL_WIDEN_PROMPT = (
    "This image is already close to 16:9. Preserve the existing image exactly as it is. "
    "Widen only the extreme left and right edges by a very small amount to reach exact 16:9. "
    "Do not change any person, face, expression, body, clothing, pose, or the current composition. "
    "Only continue the outer background naturally with no seams or visible transitions."
)

SINGLE_SELFIE_PROMPT = (
    "Keep the person exactly the same, especially the face, hair, expression, clothing, and pose. "
    "Preserve the current photo exactly in the center and extend only the outdoor background on the left and right. "
    "Continue the same trees, sky, grass, or garden naturally. No new people, no face changes, no seams."
)

TWO_PERSON_PROMPT = (
    "Keep both people exactly the same, especially their faces, hair, expressions, clothing, and pose. "
    "Preserve the original photo exactly in the center and extend only the background on the left and right. "
    "Continue the same environment naturally and do not invent extra people, arms, or bodies. No seams."
)

INDOOR_FAMILY_PROMPT = (
    "Keep every original person exactly once and preserve all faces, expressions, clothing, and pose. "
    "Preserve the current family photo exactly in the center and extend only the room on the left and right. "
    "Continue the same walls, furniture, floor, and lighting naturally. Do not duplicate or invent any person. No seams."
)

OUTDOOR_FAMILY_PROMPT = (
    "Keep every original person exactly once and preserve all faces, expressions, clothing, and pose. "
    "Preserve the current family photo exactly in the center and extend only the outdoor background on the left and right. "
    "Continue the same grass, trees, sky, path, or landscape naturally. Do not duplicate or invent any person. No seams."
)

EVENT_PROMPT = (
    "Keep every visible person exactly the same, especially the faces, expressions, clothing, and pose. "
    "Preserve the current event photo exactly in the center and extend only the background on the left and right. "
    "Continue the same lights, crowd, room, or night atmosphere naturally without inventing extra people in the center. No seams."
)

GROUP_EDGE_PROMPT = (
    "This is a crowded group photo. Keep every original person exactly once and preserve the original photo unchanged in the center. "
    "Do not duplicate, extend, clone, or invent any person, face, body, arm, or clothing at the left or right edges. "
    "Expand to 16:9 by adding only empty restaurant or room background and floor space beyond the outermost people. "
    "Continue the same walls, windows, tables, chairs, lighting, and floor naturally. No seams."
)

CITY_GROUP_PROMPT = (
    "Keep every original person exactly once and preserve all faces, expressions, clothing, and pose. "
    "Preserve the current city photo exactly in the center and extend only the street, buildings, lights, and pavement on the left and right. "
    "Do not duplicate or invent any person. Keep the same city atmosphere and realistic perspective. No seams."
)

SCENIC_SINGLE_PROMPT = (
    "Keep the person exactly the same, especially the face, body, clothing, and pose. "
    "Preserve the current scenic photo exactly in the center and extend only the mountains, trees, sky, and landscape on the left and right. "
    "Do not change the person or invent extra people. Keep the same natural light and realistic depth. No seams."
)

FULL_BODY_PROMPT = (
    "Keep every person exactly the same from head to toe, especially the face, hair, expression, clothing, hands, and full-body pose. "
    "Preserve the current photo exactly in the center and extend only the hallway, room, or background on the left and right. "
    "Do not distort legs, arms, hands, or clothing. Do not invent extra people. No seams."
)

GREEN_ROOM_PROMPT = (
    "Keep every original person exactly once and preserve all faces, expressions, clothing, and pose. "
    "Preserve the current birthday photo exactly in the center and extend only the room on the left and right. "
    "Continue the same green wall, party decorations, table, and lighting naturally. Do not duplicate or invent any person. No seams."
)

GROUP_PROMPT_OVERRIDES = {
    "13.jpg": (TWO_PERSON_PROMPT, "Custom: close selfie"),
    "18.jpg": (TWO_PERSON_PROMPT, "Custom: close selfie"),
    "19.jpg": (INDOOR_FAMILY_PROMPT, "Custom: indoor family"),
    "2.jpg": (PORTRAIT_PROMPT, "Custom: portrait"),
    "2.JPG": (PORTRAIT_PROMPT, "Custom: portrait"),
    "20.jpg": (INDOOR_FAMILY_PROMPT, "Custom: indoor family"),
    "20230204_155432.jpg": (GREEN_ROOM_PROMPT, "Custom: birthday room"),
    "24.jpg": (OUTDOOR_FAMILY_PROMPT, "Custom: outdoor family"),
    "24_b.jpg": (SCENIC_SINGLE_PROMPT, "Custom: scenic single"),
    "24_c.jpg": (SINGLE_SELFIE_PROMPT, "Custom: single selfie"),
    "25.jpg": (FULL_BODY_PROMPT, "Custom: full body"),
    "26.jpg": (INDOOR_FAMILY_PROMPT, "Custom: indoor family"),
    "27_b.jpg": (TWO_PERSON_PROMPT, "Custom: two people"),
    "28.jpeg": (EVENT_PROMPT, "Custom: event"),
    "29.jpg": (TWO_PERSON_PROMPT, "Custom: two people"),
    "3.jpg": (EVENT_PROMPT, "Custom: event"),
    "3.JPG": (EVENT_PROMPT, "Custom: event"),
    "30.jpeg": (GROUP_EDGE_PROMPT, "Custom: crowded group"),
    "31.jpeg": (CITY_GROUP_PROMPT, "Custom: city group"),
    "32.jpeg": (INDOOR_FAMILY_PROMPT, "Custom: indoor family"),
    "33.jpg": (CITY_GROUP_PROMPT, "Custom: city group"),
    "4.jpg": (EVENT_PROMPT, "Custom: event"),
    "8.jpg": (INDOOR_FAMILY_PROMPT, "Custom: indoor family"),
    "9.jpg": (INDOOR_FAMILY_PROMPT, "Custom: indoor family"),
    "IMG-20150329-WA0006.jpg": (INDOOR_FAMILY_PROMPT, "Custom: indoor family"),
    "IMG-20150610-WA0010.jpg": (OUTDOOR_FAMILY_PROMPT, "Custom: outdoor family"),
    "IMG-20150610-WA0013.jpg": (OUTDOOR_FAMILY_PROMPT, "Custom: outdoor family"),
    "IMG-20170505-WA0007.jpg": (OUTDOOR_FAMILY_PROMPT, "Custom: outdoor family"),
    "IMG-20170706-WA0007.jpg": (CITY_GROUP_PROMPT, "Custom: city group"),
    "IMG-20170813-WA0013.jpg": (OUTDOOR_FAMILY_PROMPT, "Custom: outdoor family"),
    "IMG-20180317-WA0016.jpg": (TWO_PERSON_PROMPT, "Custom: close selfie"),
    "IMG-20180805-WA0011.jpg": (OUTDOOR_FAMILY_PROMPT, "Custom: outdoor family"),
    "IMG-20180911-WA0005.jpg": (OUTDOOR_FAMILY_PROMPT, "Custom: outdoor family"),
    "IMG-20200211-WA0021.jpg": (OUTDOOR_FAMILY_PROMPT, "Custom: outdoor family"),
    "IMG-20210612-WA0031.jpg": (OUTDOOR_FAMILY_PROMPT, "Custom: outdoor family"),
    "IMG-20211116-WA0015.jpg": (INDOOR_FAMILY_PROMPT, "Custom: indoor family"),
    "IMG-20211127-WA0029.jpg": (OUTDOOR_FAMILY_PROMPT, "Custom: outdoor family"),
}


def choose_extension_prompt(img, filename=None):
    if filename:
        override = GROUP_PROMPT_OVERRIDES.get(filename)
        if override is not None:
            return override
    ratio = img.width / img.height
    width_multiplier = TARGET_ASPECT_RATIO / ratio
    if ratio < 1.0:
        return PORTRAIT_PROMPT, "Portrait side extension"
    if width_multiplier <= 1.08:
        return MINIMAL_WIDEN_PROMPT, "Near-16:9 preserve"
    if width_multiplier <= 1.35:
        return PRESERVE_PROMPT, "Already wide preserve"
    return PROMPT, "Full side extension"


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
    gemini_key = os.getenv('gemini')
    if not gemini_key:
        raise RuntimeError("No 'gemini' key found in .env")
    return genai.Client(**{"api_key": gemini_key})


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
        img = ImageOps.exif_transpose(img)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        prompt, prompt_profile = choose_extension_prompt(img, filename)
        print(f"[{i+1}/{len(todo)}] {filename}: {img.size} [{prompt_profile}]", end="", flush=True)

        try:
            result = outpaint(client, img, prompt)
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
        clean_if_enabled(out)
        print(f" -> {result.size} OK")
        time.sleep(API_DELAY)

    done = len([f for f in os.listdir(OUT_DIR) if f.lower().endswith('.jpg')])
    print(f"\nDone. {done} images in {OUT_DIR}")


def run(src_dir=None, out_dir=None):
    """Programmatic entry point used by the FastAPI backend.

    Temporarily swaps module-level SRC_DIR/OUT_DIR for the call so
    main() and its helpers keep working unchanged. Phase 1
    clean_if_enabled hook (line 270 inside main) still fires per save.

    Serialised by _RUN_LOCK so concurrent FastAPI api-mode jobs can't
    race on the module globals.
    """
    global SRC_DIR, OUT_DIR
    with _RUN_LOCK:
        prev = (SRC_DIR, OUT_DIR)
        try:
            if src_dir is not None:
                SRC_DIR = str(src_dir)
            if out_dir is not None:
                OUT_DIR = str(out_dir)
            main()
        finally:
            SRC_DIR, OUT_DIR = prev


if __name__ == "__main__":
    main()
