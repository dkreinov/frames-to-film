#!/usr/bin/env python3
"""Generate left/right edge strips from a portrait image for strip-based outpainting.

Usage:
    python generate_strips.py <filename>
"""
import os
import sys
from PIL import Image, ImageOps

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
STRIPS_DIR = os.path.join(SRC_DIR, "strips")

TARGET_W, TARGET_H = 4032, 3024
STRIP_WIDTH = 300
JPEG_QUALITY = 95

ROTATION_OVERRIDES = {
    "20260220_183711.jpg": 90,
}


def fit_image(img):
    iw, ih = img.size
    scale = min(TARGET_W / iw, TARGET_H / ih)
    new_w, new_h = int(iw * scale), int(ih * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_strips.py <filename>")
        sys.exit(1)

    filename = sys.argv[1]
    filepath = os.path.join(SRC_DIR, filename)
    if not os.path.isfile(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    os.makedirs(STRIPS_DIR, exist_ok=True)

    img = Image.open(filepath)
    img = ImageOps.exif_transpose(img)
    if filename in ROTATION_OVERRIDES:
        img = img.rotate(ROTATION_OVERRIDES[filename], expand=True)
    if img.mode != 'RGB':
        img = img.convert('RGB')

    fitted = fit_image(img)
    fw, fh = fitted.size
    gap = (TARGET_W - fw) // 2

    print(f"Original: {img.size} -> Fitted: {fw}x{fh}")
    print(f"Gap per side: {gap}px")
    print(f"Strip width: {STRIP_WIDTH}px")

    base = os.path.splitext(filename)[0]

    left_strip = fitted.crop((0, 0, STRIP_WIDTH, fh))
    left_path = os.path.join(STRIPS_DIR, f"{base}_left.jpg")
    left_strip.save(left_path, "JPEG", quality=JPEG_QUALITY)
    print(f"Left strip:  {left_strip.size} -> {left_path}")

    right_strip = fitted.crop((fw - STRIP_WIDTH, 0, fw, fh))
    right_path = os.path.join(STRIPS_DIR, f"{base}_right.jpg")
    right_strip.save(right_path, "JPEG", quality=JPEG_QUALITY)
    print(f"Right strip: {right_strip.size} -> {right_path}")


if __name__ == "__main__":
    main()
