import os
import cv2
from PIL import Image, ExifTags

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
EXTENSIONS = {'.jpg', '.jpeg', '.png'}

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def get_exif_orientation(img):
    try:
        exif = img._getexif()
        if exif:
            for tag, val in exif.items():
                if ExifTags.TAGS.get(tag) == 'Orientation':
                    return val
    except Exception:
        pass
    return None

def detect_faces(filepath):
    gray = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return 0, []
    h, w = gray.shape
    # Scale down for speed if large
    scale = 1.0
    if max(h, w) > 2000:
        scale = 2000 / max(h, w)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)))
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    # Scale bounding boxes back to original
    if scale != 1.0 and len(faces) > 0:
        faces = [[int(x / scale), int(y / scale), int(wf / scale), int(hf / scale)] for x, y, wf, hf in faces]
    return len(faces), faces

def analyze():
    files = sorted(f for f in os.listdir(SRC_DIR)
                   if os.path.isfile(os.path.join(SRC_DIR, f))
                   and os.path.splitext(f)[1].lower() in EXTENSIONS)

    TARGET_RATIO = 4 / 3
    print(f"{'Filename':<62} {'WxH':>11} {'Ratio':>6} {'EXIF':>5} {'Faces':>5} {'Status'}")
    print("-" * 110)

    for f in files:
        path = os.path.join(SRC_DIR, f)
        img = Image.open(path)
        w, h = img.size
        ratio = w / h
        orientation = get_exif_orientation(img)
        face_count, _ = detect_faces(path)

        is_landscape_43 = abs(ratio - TARGET_RATIO) / TARGET_RATIO < 0.01
        status = "OK (4:3)" if is_landscape_43 else "NEEDS CONVERSION"

        orient_str = str(orientation) if orientation else "-"
        print(f"{f:<62} {w:>5}x{h:<5} {ratio:>6.3f} {orient_str:>5} {face_count:>5} {status}")

    print(f"\nTotal: {len(files)} images")

if __name__ == "__main__":
    analyze()
