#!/usr/bin/env python3
"""Outpaint portrait images to 4:3 landscape using Gemini Pro AI.

Usage:
    python outpaint_images.py [filename]       # Single file
    python outpaint_images.py                   # All portrait images
"""
import os
import sys
import json
import time
from io import BytesIO
from dotenv import load_dotenv
from PIL import Image, ImageOps
from google import genai
from google.genai import types

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SRC_DIR, "outpainted")
SCORES_PATH = os.path.join(OUT_DIR, "scores.json")

TARGET_W, TARGET_H = 4032, 3024
TARGET_RATIO = TARGET_W / TARGET_H
RATIO_TOLERANCE = 0.01
JPEG_QUALITY = 95
EXTENSIONS = {'.jpg', '.jpeg', '.png'}
API_DELAY = 10

IMAGE_MODEL = "gemini-3-pro-image-preview"
JUDGE_MODEL = "gemini-2.0-flash"

ROTATION_OVERRIDES = {
    "20260220_183711.jpg": 90,
}

IMAGE_PROMPTS = {
    "1772197775009-c3667866-c93f-42ea-916e-2dc9008f9ad6.jpg": (
        "Extend this black and white studio portrait photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman's face, expression, body pose, hands, dress, and every detail must remain exactly as they are -- do not alter the person at all. "
        "Only extend the dark draped fabric backdrop on the left and right sides. Continue the fabric folds, creases on the floor, lighting gradient, and film grain naturally. No seams, no visible transitions."
    ),
    "1772197885222-7fe74a34-e185-4fcc-8b3a-d2f94e77e120_.jpg": (
        "Extend this black and white studio portrait to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman in the hat, her face, expression, pose, legs, clothing, and heels must remain exactly as they are -- do not alter the person at all. "
        "Only extend the dark studio backdrop and the draped fabric on the floor on both sides. Continue the same lighting with the bright rim light on the upper left. Match the film grain and contrast. No seams."
    ),
    "1772197925936-62f2481d-3ec9-4bb6-8786-84c609e19b88.jpg": (
        "Extend this black and white studio portrait to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman with long hair in shorts and dark top must remain exactly as she is -- do not alter the person at all. "
        "Only extend the dark fabric backdrop on both sides. Continue the same folds, lighting, and film grain. No seams, no visible transitions."
    ),
    "1772197984962-3ae78550-f21d-4161-9b97-0b3ff223ceb4_.jpg": (
        "Extend this black and white studio portrait to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman in the wrap dress sitting and holding her leg must remain exactly as she is -- do not alter the person at all. "
        "Only extend the dark draped fabric backdrop and floor fabric on both sides. Match the lighting, creased fabric texture, and film grain. No seams."
    ),
    "1772198063666-c10e8380-6c25-428d-8ab4-86efcac888e2.jpg": (
        "Extend this sepia-toned portrait photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The smiling young woman's face, expression, hair, blazer, and every detail must remain exactly as they are -- do not alter the person at all. "
        "Only extend the light plain background on both sides. Continue the same smooth gradient and warm sepia tone. Match the photographic style and grain. No seams."
    ),
    "1772198098447-1d14e37f-b754-4cac-a068-e572aa20a23b_.jpg": (
        "Extend this black and white close-up portrait to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman's face, white knitted hat, dark scarf, smile, eyes, and mole must remain exactly as they are -- do not alter the person at all. "
        "Only extend the blurred background on both sides. Continue the same soft bokeh, tonal range, and film grain. No seams."
    ),
    "1772198174166-4ea4886b-f0b1-4253-b6c4-b80f3c8a2575_.jpg": (
        "Extend this black and white portrait photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The person's face, expression, eyes, lips, hair, mole, and every detail must remain exactly as they are -- do not alter the person at all. "
        "Only extend the dark studio background on the left and right sides. Continue the soft gradient lighting, film grain, and photographic style of the original. No seams, no visible transitions."
    ),
    "1772198672597-be295115-bd15-4fc1-b484-41699fbeb994.jpg": (
        "This photograph shows two photos side by side. Extend the entire image to 4:3 landscape aspect ratio. "
        "On the left side, extend the stairway and building scene. On the right side, extend the dark stage with curtains. "
        "Both people must remain exactly as they are -- do not alter their faces, expressions, bodies, or clothing in any way. "
        "Only extend the backgrounds on the outer edges. Match the color tones and photographic style of each respective photo."
    ),
    "20260220_183808.jpg": (
        "Extend this vintage black and white photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The little girl with the bow, her face, smile, doll, and clothing must remain exactly as they are -- do not alter the people at all. "
        "Only extend the couch, cushions, and room interior on both sides. Continue the same fabric texture, lighting, and vintage photographic quality. No seams."
    ),
    "20260220_183841.jpg": (
        "Extend this vintage sepia photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The little girl with the white bow, her face, smile, bib, and clothing must remain exactly as they are -- do not alter the child at all. "
        "Only extend the lace curtain and room interior on both sides. Continue the floral curtain pattern, warm sepia tone, and vintage quality. No seams."
    ),
    "20260220_183907.jpg": (
        "Extend this faded vintage color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The smiling girl with pink bows and floral dress must remain exactly as she is -- do not alter the child at all. "
        "Only extend the garden foliage background on both sides. Continue the same faded color tones, leaves, and vintage photographic style. No seams."
    ),
    "20260220_184034.jpg": (
        "Extend this faded vintage photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The girl with the red bow and dark school uniform with white collar must remain exactly as she is -- do not alter the child at all. "
        "Only extend the light background and fern foliage on both sides. Match the reddish faded color cast and vintage quality. No seams."
    ),
    "20260220_184155.jpg": (
        "Extend this sepia-toned portrait to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The smiling young woman with her chin resting on her hand, wearing a patterned sweater, must remain exactly as she is -- do not alter the person at all. "
        "Only extend the light background on both sides. Continue the warm sepia tone and vintage quality. No seams."
    ),
    "20260220_184209.jpg": (
        "Extend this faded vintage color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "Both people -- the young woman and the girl hugging her -- must remain exactly as they are -- do not alter either person at all. "
        "Only extend the wooden-paneled room interior on both sides. Continue the warm faded tones and indoor lighting. No seams."
    ),
    "20260220_184216.jpg": (
        "Extend this faded sepia photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The young woman among tree branches, wearing a light coat with buttons, must remain exactly as she is -- do not alter the person at all. "
        "Only extend the tree branches, leaves, and natural background on both sides. Match the warm reddish-sepia color cast and vintage quality. No seams."
    ),
    "20260220_184231.jpg": (
        "Extend this sepia photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The young woman with short bangs and white collar must remain exactly as she is -- do not alter the person at all. "
        "Only extend the garden scene with the chain-link fence and foliage on both sides. Match the warm sepia tone and vintage style. No seams."
    ),
    "20260220_184310.jpg": (
        "Extend this sepia vintage photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The toddler with the bow and floral dress must remain exactly as she is -- do not alter the child at all. "
        "Only extend the blurred background on both sides. Continue the warm yellow-sepia tone and vintage quality. No seams."
    ),
    "20260220_184336.jpg": (
        "Extend this faded vintage color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The girl with the bow and floral pattern dress must remain exactly as she is -- do not alter the child at all. "
        "Only extend the grass and natural outdoor background on both sides. Match the faded warm color tones and vintage quality. No seams."
    ),
    "20260220_184353.jpg": (
        "Extend this vintage color portrait to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The smiling young woman with the lace shawl and dark dress must remain exactly as she is -- do not alter the person at all. "
        "Only extend the plain light background on both sides. Continue the warm faded tones and vintage studio quality. No seams."
    ),
    "20260227_152648.jpg": (
        "Extend this color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "All three people standing together must remain exactly as they are -- do not alter any person at all. "
        "Only extend the tropical plant foliage and indoor lobby/atrium setting on both sides. Continue the same lighting, colors, and photographic style. No seams."
    ),
    "20260227_153302.jpg": (
        "Extend this vintage black and white photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The little girl with pigtails and bows, wearing the embroidered dress, must remain exactly as she is -- do not alter the child at all. "
        "Only extend the light background on both sides. Keep the same creased/aged photo texture, tonal range, and vintage quality. No seams."
    ),
    "20260227_153327.jpg": (
        "Extend this black and white portrait to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The smiling woman in the white ruffled blouse with earrings must remain exactly as she is -- do not alter the person at all. "
        "Only extend the plain light studio background on both sides. Match the same tonal range and photographic style. No seams."
    ),
    "20260227_153417.jpg": (
        "Extend this color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman in the blue striped shirt eating the cappuccino must remain exactly as she is -- do not alter the person at all. "
        "Only extend the cafe interior on both sides -- wood paneling, chairs, the glass display case, and counter. Match the warm indoor lighting and colors. No seams."
    ),
    "20260227_153608.jpg": (
        "Extend this color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman in the white blouse and pink pants presenting at the board must remain exactly as she is -- do not alter the person at all. "
        "Only extend the classroom setting on both sides -- the blue wall, the teaching board with Hebrew text, and the curtains. Match the indoor lighting and colors. No seams."
    ),
    "20260227_153700.jpg": (
        "Extend this color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman in the floral dress must remain exactly as she is -- do not alter the person at all. "
        "Only extend the apartment living room on both sides -- white walls, dark furniture, doorway, and wall calendar. Match the flash photography style and colors. No seams."
    ),
    "20260227_153729.jpg": (
        "Extend this color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman dancing in the purple outfit must remain exactly as she is -- do not alter the person at all. "
        "Only extend the living room on both sides -- the wooden bookshelf, TV, rug, and wall. Match the indoor lighting and colors. No seams."
    ),
    "20260227_153849.jpg": (
        "Extend this color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman in denim overalls and beret holding a cup must remain exactly as she is -- do not alter the person at all. "
        "Only extend the room interior on both sides -- the chairs, shelf, flowers, and TV area. Match the flash photography lighting and colors. No seams."
    ),
    "20260227_174911.jpg": (
        "Extend this color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "All people at the table must remain exactly as they are -- do not alter any person at all. "
        "Only extend the scene on both sides -- the table with white tablecloth, the decorative carpet/rug on the wall, and the room. Match the warm indoor lighting and colors. No seams."
    ),
    "20260227_175049.jpg": (
        "Extend this color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "Both women hugging must remain exactly as they are -- do not alter either person at all. "
        "Only extend the bedroom scene on both sides -- the blue floral curtains, bedding, lamp, and wall. Match the warm indoor lighting and colors. No seams."
    ),
    "20260227_175252.jpg": (
        "Extend this color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman in the fur coat and hat smiling in the doorway must remain exactly as she is -- do not alter the person at all. "
        "Only extend the hallway on both sides -- the pink wallpaper, wooden door frame, and walls. Match the warm indoor lighting and colors. No seams."
    ),
    "20260227_175406.jpg": (
        "Extend this color photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "Both women must remain exactly as they are -- do not alter either person at all. "
        "Only extend the apartment room on both sides -- the wallpaper, poster, and walls. Match the warm indoor lighting and colors. No seams."
    ),
    "5189965189_16ec2e8ba2_b.jpg": (
        "Extend this wedding photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The bride in the white dress and veil and the groom in the beige suit must remain exactly as they are -- do not alter either person at all. "
        "Only extend the fairy-light curtain backdrop on both sides. Continue the warm golden sparkle lights and draped fabric. No seams."
    ),
    "5190026227_36ae2e0a2a_b.jpg": (
        "Extend this wedding photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The bride, groom holding the ketubah, and the woman in the pink dress must remain exactly as they are -- do not alter any person at all. "
        "Only extend the fairy-light curtain backdrop on both sides. Continue the warm golden sparkle lights. No seams."
    ),
    "5190668344_65af8357de_b.jpg": (
        "Extend this wedding ceremony photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "All people -- the bride, groom, and all guests -- must remain exactly as they are -- do not alter any person at all. "
        "Only extend the chuppah canopy, fairy-light backdrop, and white fabric on both sides. Match the warm indoor lighting. No seams."
    ),
    "5191494168_f37d91b414_b.jpg": (
        "Extend this wedding party photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "Both women hugging and all other people in the background must remain exactly as they are -- do not alter any person at all. "
        "Only extend the dance hall scene on both sides -- the crowd, the projector screen, and the venue walls. Match the flash photography and warm party lighting. No seams."
    ),
    "8580854764_e741b9bdc8_b.jpg": (
        "Extend this outdoor street photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman with sunglasses pushing the red double stroller must remain exactly as she is -- do not alter the person at all. "
        "Only extend the sidewalk, road, buildings, trees, and urban streetscape on both sides. Match the overcast daylight and colors. No seams."
    ),
    "8580900926_506a631742_b.jpg": (
        "Extend this indoor photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The man in the blue t-shirt holding the newborn baby must remain exactly as they are -- do not alter any person at all. "
        "Only extend the living room scene on both sides -- the leather armchairs, side table, window, and baby supplies. Match the flash photography and indoor lighting. No seams."
    ),
    "8580902112_2ec3566be0_b.jpg": (
        "Extend this photograph of twin babies to a 4:3 landscape aspect ratio by widening it horizontally. "
        "Both babies with pacifiers and the Hebrew flashcards must remain exactly as they are -- do not alter any person or card at all. "
        "Only extend the bedding, blankets, and surrounding baby items on both sides. Match the indoor flash lighting and colors. No seams."
    ),
    "A 005.jpg": (
        "Extend this indoor nighttime photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The smiling woman in the gray sweater standing by the window must remain exactly as she is -- do not alter the person at all. "
        "Only extend the apartment interior on both sides -- the window with city lights, lace curtain, and floor. Match the warm indoor flash lighting. No seams."
    ),
    "A 011.jpg": (
        "Extend this close-up photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The person's body and the drawings on the belly must remain exactly as they are -- do not alter the person or the artwork at all. "
        "Only extend the dark indoor background on both sides -- the couch, the room. Match the flash lighting and warm tones. No seams."
    ),
    "A 021.jpg": (
        "Extend this indoor photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "Both people -- the man in the hoodie and the woman showing her belly with drawings -- must remain exactly as they are -- do not alter either person at all. "
        "Only extend the living room on both sides -- the leather couch, tiled floor, wall art, and ceiling. Match the flash photography lighting. No seams."
    ),
    "IMG_0182.jpg": (
        "Extend this outdoor viewpoint photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "The woman in the blue t-shirt and black pants standing at the railing must remain exactly as she is -- do not alter the person at all. "
        "Only extend the panoramic view, metal railing, concrete walkway, sky and clouds on both sides. Match the bright daylight and colors. No seams."
    ),
    "IMG_0215.jpg": (
        "Extend this mirror selfie photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
        "Both people reflected in the mirror -- the woman in the yellow dress and the man in the gray blazer -- must remain exactly as they are -- do not alter any person at all. "
        "Only extend the wall and mirror frame area on both sides. Continue the white wall, the edge of the mirror, and any room elements. Match the indoor lighting. No seams."
    ),
}

FALLBACK_PROMPT = (
    "Extend this photograph to a 4:3 landscape aspect ratio by widening it horizontally. "
    "Every person's face, expression, body, and clothing must remain exactly as they are -- do not alter any person at all. "
    "Only extend the background on both sides naturally. Match the existing lighting, colors, textures, and photographic style. No seams, no visible transitions."
)

JUDGE_PROMPT = """\
You are a strict image quality judge. You will receive TWO images:
1. FIRST image: the ORIGINAL portrait photograph
2. SECOND image: the OUTPAINTED version (extended to landscape)

Compare them carefully and score on these 4 axes (1-10 each). Be strict -- \
deduct points for ANY deviation:

1. seamlessness: Is there a visible seam, boundary, or abrupt transition where \
the original content meets the generated extension? (10 = invisible, 5 = noticeable, 1 = obvious line)
2. style_match: Does the extended area match the original's lighting direction, \
color temperature, film grain, and photographic era? Are the extended objects/surfaces \
plausible for the scene? (10 = perfect match, 5 = close but off, 1 = completely different)
3. person_preservation: Compare the person in BOTH images pixel by pixel. \
Is the face IDENTICAL? Same expression? Same eye position? Same mouth shape? \
Same hair? Same clothing folds? Same hand position? Same objects held? \
ANY change, even subtle, should score below 8. (10 = identical, 7 = very subtle change, \
5 = noticeable change, 1 = different person)
4. naturalness: Does the FULL outpainted image look like a real photograph? \
Are there any AI artifacts, impossible geometry, or unnatural elements in the \
extended areas? (10 = completely real, 5 = some oddities, 1 = obviously AI)

Respond ONLY with valid JSON, no other text:
{"seamlessness": N, "style_match": N, "person_preservation": N, "naturalness": N}
"""


def get_client():
    api_key = os.getenv('gemini')
    if not api_key:
        print("ERROR: No 'gemini' key found in .env", file=sys.stderr)
        sys.exit(1)
    return genai.Client(api_key=api_key)


def is_target_ratio(w, h):
    if h == 0:
        return False
    return abs(w / h - TARGET_RATIO) / TARGET_RATIO < RATIO_TOLERANCE


def load_image(filepath, filename):
    img = Image.open(filepath)
    img = ImageOps.exif_transpose(img)
    if filename in ROTATION_OVERRIDES:
        img = img.rotate(ROTATION_OVERRIDES[filename], expand=True)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    return img


def outpaint(client, img, prompt):
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    pil_for_api = Image.open(buf)

    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[prompt, pil_for_api],
        config=types.GenerateContentConfig(
            response_modalities=["Text", "Image"]
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            result = Image.open(BytesIO(part.inline_data.data))
            if result.mode != 'RGB':
                result = result.convert('RGB')
            return result

    return None


def upscale_if_needed(img):
    w, h = img.size
    if w >= TARGET_W and h >= TARGET_H:
        return img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    scale = max(TARGET_W / w, TARGET_H / h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - TARGET_W) // 2
    top = (new_h - TARGET_H) // 2
    return img.crop((left, top, left + TARGET_W, top + TARGET_H))


def judge(client, original_img, outpainted_img):
    buf_orig = BytesIO()
    original_img.save(buf_orig, format="JPEG", quality=85)
    buf_orig.seek(0)
    pil_orig = Image.open(buf_orig)

    buf_out = BytesIO()
    outpainted_img.save(buf_out, format="JPEG", quality=85)
    buf_out.seek(0)
    pil_out = Image.open(buf_out)

    response = client.models.generate_content(
        model=JUDGE_MODEL,
        contents=[JUDGE_PROMPT, pil_orig, pil_out],
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        scores = json.loads(text)
        avg = sum(scores.values()) / len(scores)
        scores["average"] = round(avg, 1)
        return scores
    except (json.JSONDecodeError, AttributeError):
        print(f"    Judge returned unparseable response: {text[:200]}")
        return {"seamlessness": 5, "style_match": 5, "person_preservation": 5,
                "naturalness": 5, "average": 5.0, "parse_error": True}


def process_single(client, filename, all_scores):
    src_path = os.path.join(SRC_DIR, filename)
    out_path = os.path.join(OUT_DIR, os.path.splitext(filename)[0] + ".jpg")

    if not os.path.isfile(src_path):
        print(f"  SKIP  {filename} -- not found")
        return

    img = load_image(src_path, filename)
    w, h = img.size

    if is_target_ratio(w, h):
        result = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
        result.save(out_path, "JPEG", quality=JPEG_QUALITY)
        print(f"  COPY  {filename:<55} (already 4:3)")
        all_scores[filename] = {"action": "copy", "scores": None}
        return

    prompt = IMAGE_PROMPTS.get(filename, FALLBACK_PROMPT)
    print(f"  {filename:<55} {w}x{h}", flush=True)

    try:
        result = outpaint(client, img, prompt)
    except Exception as e:
        print(f"  FAIL  {filename} -- API ERROR: {e}")
        all_scores[filename] = {"action": "failed", "scores": None}
        time.sleep(API_DELAY)
        return

    if result is None:
        print(f"  FAIL  {filename} -- no image returned")
        all_scores[filename] = {"action": "failed", "scores": None}
        time.sleep(API_DELAY)
        return

    result = upscale_if_needed(result)
    result.save(out_path, "JPEG", quality=JPEG_QUALITY)
    print(f"  OK    {filename:<55} -> {result.size[0]}x{result.size[1]}")
    all_scores[filename] = {"action": "pro_outpaint", "scores": None}


def get_image_files():
    return sorted(
        f for f in os.listdir(SRC_DIR)
        if os.path.isfile(os.path.join(SRC_DIR, f))
        and os.path.splitext(f)[1].lower() in EXTENSIONS
    )


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    client = get_client()

    all_scores = {}
    if os.path.exists(SCORES_PATH):
        with open(SCORES_PATH, 'r') as f:
            all_scores = json.load(f)

    if len(sys.argv) > 1:
        files = [sys.argv[1]]
    else:
        already_done = set(all_scores.keys())
        files = [f for f in get_image_files() if f not in already_done]

    print(f"Outpainting {len(files)} images -> {OUT_DIR}")
    print(f"Model: {IMAGE_MODEL} | Judge: {JUDGE_MODEL}")
    print("-" * 80)

    for f in files:
        process_single(client, f, all_scores)
        with open(SCORES_PATH, 'w') as fh:
            json.dump(all_scores, fh, indent=2)

    total = len([f for f in os.listdir(OUT_DIR) if f.lower().endswith('.jpg')])
    print("-" * 80)
    print(f"Done. {total} images in {OUT_DIR}")


if __name__ == "__main__":
    main()
