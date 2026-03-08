import os
import sys
from PIL import Image, ImageOps, ImageFilter, ImageEnhance

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SRC_DIR = ROOT_DIR
OUT_DIR = os.path.join(ROOT_DIR, "processed")
TARGET_W, TARGET_H = 4032, 3024
TARGET_RATIO = TARGET_W / TARGET_H  # 1.333...
RATIO_TOLERANCE = 0.01
BLUR_RADIUS = 50
DARKEN_FACTOR = 0.6  # 1.0 = no change, 0.0 = black
JPEG_QUALITY = 95
EXTENSIONS = {'.jpg', '.jpeg', '.png'}

# Manual rotation overrides (degrees CCW) for images where EXIF is wrong.
# Typical case: phone photo of a physical landscape photo taken in portrait mode.
ROTATION_OVERRIDES = {
    "20260220_183711.jpg": 90,
}


def is_target_ratio(w, h):
    if h == 0:
        return False
    ratio = w / h
    return abs(ratio - TARGET_RATIO) / TARGET_RATIO < RATIO_TOLERANCE


def create_blurred_background(img):
    """Scale image to fill target canvas (crop-to-fill), blur, and darken."""
    iw, ih = img.size
    scale = max(TARGET_W / iw, TARGET_H / ih)
    scaled_w, scaled_h = int(iw * scale), int(ih * scale)
    stretched = img.resize((scaled_w, scaled_h), Image.LANCZOS)

    left = (scaled_w - TARGET_W) // 2
    top = (scaled_h - TARGET_H) // 2
    cropped = stretched.crop((left, top, left + TARGET_W, top + TARGET_H))

    blurred = cropped.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))
    darkened = ImageEnhance.Brightness(blurred).enhance(DARKEN_FACTOR)
    return darkened


def fit_image(img):
    """Scale image to fit within target canvas, preserving aspect ratio."""
    iw, ih = img.size
    scale = min(TARGET_W / iw, TARGET_H / ih)
    new_w, new_h = int(iw * scale), int(ih * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)


def process_image(filepath, filename):
    """Process a single image. Returns (action, details) tuple."""
    img = Image.open(filepath)
    img = ImageOps.exif_transpose(img)

    if filename in ROTATION_OVERRIDES:
        degrees = ROTATION_OVERRIDES[filename]
        img = img.rotate(degrees, expand=True)

    if img.mode != 'RGB':
        img = img.convert('RGB')

    w, h = img.size

    if is_target_ratio(w, h):
        result = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
        return result, "copy (resized to exact target)"

    bg = create_blurred_background(img)
    fg = fit_image(img)
    fw, fh = fg.size

    x_offset = (TARGET_W - fw) // 2
    y_offset = (TARGET_H - fh) // 2
    bg.paste(fg, (x_offset, y_offset))

    return bg, f"blur-pad ({w}x{h} -> {TARGET_W}x{TARGET_H}, fg={fw}x{fh})"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    files = sorted(f for f in os.listdir(SRC_DIR)
                   if os.path.isfile(os.path.join(SRC_DIR, f))
                   and os.path.splitext(f)[1].lower() in EXTENSIONS)

    print(f"Processing {len(files)} images -> {OUT_DIR}")
    print(f"Target: {TARGET_W}x{TARGET_H} (4:3 landscape)")
    print("-" * 80)

    for f in files:
        src_path = os.path.join(SRC_DIR, f)
        out_path = os.path.join(OUT_DIR, os.path.splitext(f)[0] + ".jpg")

        try:
            result, action = process_image(src_path, f)
            result.save(out_path, "JPEG", quality=JPEG_QUALITY)
            print(f"  OK  {f:<60} {action}")
        except Exception as e:
            print(f"FAIL  {f:<60} {e}", file=sys.stderr)

    out_files = [f for f in os.listdir(OUT_DIR) if f.lower().endswith('.jpg')]
    print("-" * 80)
    print(f"Done. {len(out_files)} images in {OUT_DIR}")


if __name__ == "__main__":
    main()
