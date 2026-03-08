import os
import base64
import cv2
from io import BytesIO
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SRC_DIR = ROOT_DIR
PROC_DIR = os.path.join(ROOT_DIR, "processed")
REPORT_PATH = os.path.join(PROC_DIR, "qa_report.html")
EXTENSIONS = {'.jpg', '.jpeg', '.png'}
THUMB_W = 500

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')


def detect_faces(filepath):
    gray = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return 0
    h, w = gray.shape
    scale = 1.0
    if max(h, w) > 2000:
        scale = 2000 / max(h, w)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)))
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return len(faces)


def img_to_base64_thumb(filepath, max_w=THUMB_W):
    img = Image.open(filepath)
    ratio = max_w / img.width
    img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def generate_report():
    files = sorted(f for f in os.listdir(SRC_DIR)
                   if os.path.isfile(os.path.join(SRC_DIR, f))
                   and os.path.splitext(f)[1].lower() in EXTENSIONS)

    rows = []
    regressions = []

    for f in files:
        src_path = os.path.join(SRC_DIR, f)
        proc_name = os.path.splitext(f)[0] + ".jpg"
        proc_path = os.path.join(PROC_DIR, proc_name)

        if not os.path.exists(proc_path):
            rows.append((f, "MISSING", 0, 0))
            continue

        orig_faces = detect_faces(src_path)
        proc_faces = detect_faces(proc_path)
        status = "OK" if proc_faces >= orig_faces else "REGRESSION"

        if status == "REGRESSION":
            regressions.append(f)

        orig_b64 = img_to_base64_thumb(src_path)
        proc_b64 = img_to_base64_thumb(proc_path)

        rows.append((f, status, orig_faces, proc_faces, orig_b64, proc_b64))

    print(f"Images checked: {len(rows)}")
    print(f"Face regressions: {len(regressions)}")
    if regressions:
        for r in regressions:
            print(f"  WARNING: {r}")

    html = ['<!DOCTYPE html><html><head><meta charset="utf-8">']
    html.append('<title>Olga Movie - QA Report</title>')
    html.append('<style>')
    html.append('body{font-family:Arial,sans-serif;margin:20px;background:#1a1a1a;color:#eee}')
    html.append('.pair{display:flex;gap:20px;margin:20px 0;padding:15px;background:#2a2a2a;border-radius:8px}')
    html.append('.pair img{border-radius:4px;max-height:400px}')
    html.append('.label{font-size:12px;color:#aaa;margin-bottom:4px}')
    html.append('.ok{border-left:4px solid #4CAF50}')
    html.append('.regression{border-left:4px solid #f44336}')
    html.append('h1{color:#fff}h3{margin:0 0 5px}')
    html.append('.meta{font-size:13px;color:#888;margin-top:5px}')
    html.append('</style></head><body>')
    html.append(f'<h1>Olga Movie - QA Report</h1>')
    html.append(f'<p>{len(rows)} images | {len(regressions)} face regressions</p>')

    for entry in rows:
        if len(entry) == 4:
            f, status, _, _ = entry
            html.append(f'<div class="pair"><h3>{f} - {status}</h3></div>')
            continue

        f, status, orig_faces, proc_faces, orig_b64, proc_b64 = entry
        css_class = "ok" if status == "OK" else "regression"
        html.append(f'<div class="pair {css_class}">')
        html.append(f'<div><div class="label">Original</div><img src="data:image/jpeg;base64,{orig_b64}"><div class="meta">Faces: {orig_faces}</div></div>')
        html.append(f'<div><div class="label">Processed (4032x3024)</div><img src="data:image/jpeg;base64,{proc_b64}"><div class="meta">Faces: {proc_faces}</div></div>')
        html.append(f'<div><h3>{f}</h3><div class="meta">Status: {status}</div><div class="meta">Faces: {orig_faces} -> {proc_faces}</div></div>')
        html.append('</div>')

    html.append('</body></html>')

    with open(REPORT_PATH, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(html))

    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    generate_report()
