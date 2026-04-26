"""Benchmark image-edit quality across vendors with same prompts per task.

Tasks:
    T1 EXTEND      — outpaint vintage portrait to 16:9, preserve color/identity
    T2 OUTFIT_SWAP — replace dress with different outfit, B&W glamour
    T3 RECOMPOSE   — wedding scene, fill cropped figure at bottom-right
    T4 ADD_ITEM    — cafe portrait, add transition prop

Models:
    gemini-2.5-flash-image-preview   (Nano Banana)     $0.039/img
    gemini-3-pro-image-preview       (Nano Banana Pro) $0.134/img
    gpt-image-2 (medium, 1024x1024)                    $0.053/img
    qwen-image-edit (DashScope SG)                     ~$0.025/img

Outputs: benchmarks/image_edit_2026-04-26/{model}/{task}.png + summary.md
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

OUT_BASE = ROOT / "benchmarks" / "image_edit_2026-04-26"
SOURCES_DIR = ROOT / "projects" / "olga" / "inputs"

# ---------- Tasks ----------

@dataclass
class Task:
    id: str
    src: str
    prompt: str
    is_outpaint: bool = False  # affects gpt-image-2 path (mask vs instruction)
    target_aspect: tuple[int, int] | None = None  # (w, h) when outpaint

TASKS: list[Task] = [
    Task(
        id="T1_extend",
        src="20260220_183907.jpg",
        prompt=(
            "Extend this vintage photograph to 16:9 widescreen by widening it "
            "horizontally. Preserve the person, face, expression, hair, hair-bow, "
            "clothing, and pose exactly. Match the existing faded vintage color "
            "palette (warm sepia and red tones), film grain, and aged photographic "
            "feel. Continue the surrounding background naturally on both sides. "
            "No seams, no color shift, no new people."
        ),
        is_outpaint=True,
        target_aspect=(16, 9),
    ),
    Task(
        id="T2_outfit_swap",
        src="1772197775009-c3667866-c93f-42ea-916e-2dc9008f9ad6.jpg",
        prompt=(
            "Replace the dress with a tailored black turtleneck sweater and "
            "high-waisted black trousers. Keep the woman's face, hair, makeup, "
            "earrings, pose, and the studio backdrop and lighting exactly the same. "
            "Preserve the black-and-white film aesthetic and the high-fashion "
            "studio-photography mood."
        ),
    ),
    Task(
        id="T3_recompose",
        src="5190668344_65af8357de_b.jpg",
        prompt=(
            "Recompose this wedding photograph: the crouching man at the bottom "
            "right is partially cut off by the frame edge. Extend the bottom and "
            "right sides of the image to include him fully and cleanly. Preserve "
            "every face, expression, the bride's gown, the groom's suit, the tallit, "
            "the chuppah backdrop with string lights, and the warm golden-hour "
            "color palette. Keep all original people exactly once, no duplicates, "
            "no invented faces."
        ),
        is_outpaint=True,
        target_aspect=(4, 3),  # extend a bit on bottom + right
    ),
    Task(
        id="T4_add_item",
        src="20260227_153417.jpg",
        prompt=(
            "Add a small folded handwritten paper note resting on the counter "
            "next to the woman, partially visible with a few words written in ink. "
            "The note should look like a clue or message for a story transition. "
            "Keep the woman, her smile, hair, striped shirt, the cafe interior, "
            "all glassware and cups, the dessert she is holding, and the existing "
            "warm window light exactly unchanged."
        ),
    ),
]

# ---------- Pricing ----------

PRICING_USD: dict[str, float] = {
    "gemini-2.5-flash-image": 0.039,
    "gemini-3.1-flash-image-preview": 0.067,
    "gemini-3-pro-image-preview": 0.134,
    "gpt-image-2-medium": 0.053,
    "qwen-image-edit": 0.045,        # base tier, DashScope international
    "qwen-image-edit-plus": 0.045,   # 2509 release, 20B params
    "qwen-image-edit-max": 0.084,    # top tier (estimate; verify by billing)
}

# ---------- Source prep ----------

def load_source_canonical(src_name: str) -> Image.Image:
    path = SOURCES_DIR / src_name
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # fix rotation BEFORE sending
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    return img

def pad_to_aspect(img: Image.Image, ar_w: int, ar_h: int) -> tuple[Image.Image, Image.Image]:
    """Pad RGBA canvas to target aspect ratio. Returns (padded_rgba, mask).
    Mask: white = keep original (opaque), black = generate (transparent in canvas)."""
    w, h = img.size
    target = ar_w / ar_h
    cur = w / h
    if cur < target:
        new_w = int(round(h * target))
        new_h = h
    else:
        new_w = w
        new_h = int(round(w / target))
    canvas = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
    off_x = (new_w - w) // 2
    off_y = (new_h - h) // 2
    rgba = img.convert("RGBA")
    canvas.paste(rgba, (off_x, off_y))
    mask = Image.new("L", (new_w, new_h), 0)
    inner = Image.new("L", (w, h), 255)
    mask.paste(inner, (off_x, off_y))
    return canvas, mask

def img_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def img_to_compact_bytes(img: Image.Image, max_long_edge: int = 2048,
                         max_bytes: int = 9_500_000) -> tuple[bytes, str]:
    """Return (bytes, mime). Resized + JPEG-encoded to fit DashScope 10MB cap."""
    w, h = img.size
    long_edge = max(w, h)
    if long_edge > max_long_edge:
        scale = max_long_edge / long_edge
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    rgb = img.convert("RGB")
    quality = 92
    while quality >= 60:
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        if len(data) <= max_bytes:
            return data, "image/jpeg"
        quality -= 5
    return data, "image/jpeg"

# ---------- Vendors ----------

@dataclass
class Result:
    model: str
    task_id: str
    ok: bool
    out_path: Path | None = None
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    error: str = ""

def gemini_edit(model_id: str, src_img: Image.Image, prompt: str) -> bytes:
    """google-genai client: pass [prompt, image]."""
    from google import genai
    key = os.environ.get("PROMPT_LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("PROMPT_LLM_API_KEY not set")
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model=model_id,
        contents=[prompt, src_img],
    )
    for cand in resp.candidates:
        for part in cand.content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                data = inline.data
                if isinstance(data, str):  # base64-encoded
                    data = base64.b64decode(data)
                return data
    raise RuntimeError(f"no image part in gemini response: {resp}")

def openai_edit(src_img: Image.Image, prompt: str, *, is_outpaint: bool,
                target_aspect: tuple[int, int] | None) -> bytes:
    """gpt-image-2 via openai SDK. Outpaint = padded canvas + mask."""
    from openai import OpenAI
    key = os.environ.get("GPT_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("GPT_KEY not set")
    client = OpenAI(api_key=key)

    if is_outpaint and target_aspect:
        canvas, mask = pad_to_aspect(src_img, *target_aspect)
        cw, ch = canvas.size
        if cw >= ch:
            target_size = (1536, 1024)
        else:
            target_size = (1024, 1536)
        canvas = canvas.resize(target_size, Image.LANCZOS).convert("RGBA")
        mask = mask.resize(target_size, Image.NEAREST)
        # OpenAI mask: RGBA PNG, alpha=0 marks the edit region (the new edge),
        # alpha=255 marks the keep region (the original-photo area).
        mask_rgba = Image.new("RGBA", target_size, (0, 0, 0, 0))
        mask_rgba.putalpha(mask)
        assert canvas.size == mask_rgba.size, (canvas.size, mask_rgba.size)
        img_bytes = img_to_png_bytes(canvas)
        mask_bytes = img_to_png_bytes(mask_rgba)
        size_str = f"{target_size[0]}x{target_size[1]}"
        result = client.images.edit(
            model="gpt-image-2",
            image=("source.png", img_bytes, "image/png"),
            mask=("mask.png", mask_bytes, "image/png"),
            prompt=prompt,
            size=size_str,
            quality="medium",
        )
    else:
        # Instruction edit (no mask) — gpt-image-2 regenerates whole canvas.
        # Resize to nearest supported size first.
        w, h = src_img.size
        if w >= h:
            tgt = (1536, 1024)
        else:
            tgt = (1024, 1536)
        resized = src_img.convert("RGB").resize(tgt, Image.LANCZOS)
        img_bytes = img_to_png_bytes(resized)
        result = client.images.edit(
            model="gpt-image-2",
            image=("source.png", img_bytes, "image/png"),
            prompt=prompt,
            size=f"{tgt[0]}x{tgt[1]}",
            quality="medium",
        )
    b64 = result.data[0].b64_json
    return base64.b64decode(b64)

def qwen_image_edit(src_img: Image.Image, prompt: str,
                    model: str = "qwen-image-edit",
                    size: str | None = None) -> bytes:
    """DashScope Singapore qwen-image-edit / -plus / -max. Sync mode."""
    key = os.environ.get("QWEEN_KEY") or os.environ.get("QWEN_KEY")
    if not key:
        raise RuntimeError("QWEEN_KEY not set")

    img_bytes, mime = img_to_compact_bytes(src_img)
    img_b64 = base64.b64encode(img_bytes).decode()
    data_uri = f"data:{mime};base64,{img_b64}"

    submit_url = (
        "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/"
        "multimodal-generation/generation"
    )
    params: dict[str, object] = {"negative_prompt": "", "watermark": False}
    if size:
        params["size"] = size
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": data_uri},
                        {"text": prompt},
                    ],
                }
            ]
        },
        "parameters": params,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    r = requests.post(submit_url, headers=headers, json=payload, timeout=180)
    if r.status_code >= 400:
        raise RuntimeError(f"dashscope sync failed {r.status_code}: {r.text[:400]}")
    body = r.json()
    output = body.get("output", {})
    choices = output.get("choices") or []
    for ch in choices:
        msg = ch.get("message", {})
        content = msg.get("content", [])
        for item in content:
            url = item.get("image")
            if url:
                img_r = requests.get(url, timeout=60)
                img_r.raise_for_status()
                return img_r.content
            b64 = item.get("image_base64") or item.get("data")
            if b64:
                return base64.b64decode(b64)
    raise RuntimeError(f"no image in dashscope sync response: {body}")

# ---------- Driver ----------

MODELS_TO_RUN = [
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
    "gpt-image-2-medium",
    "qwen-image-edit",
    "qwen-image-edit-plus",
    "qwen-image-edit-max",
]

def estimate_total_cost(models: list[str], n_tasks: int) -> float:
    return sum(PRICING_USD[m] * n_tasks for m in models)

def run_one(model: str, task: Task) -> Result:
    out_dir = OUT_BASE / model
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{task.id}.png"
    src_img = load_source_canonical(task.src)

    t0 = time.time()
    try:
        if model.startswith("gemini-"):
            data = gemini_edit(model, src_img, task.prompt)
        elif model == "gpt-image-2-medium":
            data = openai_edit(src_img, task.prompt,
                               is_outpaint=task.is_outpaint,
                               target_aspect=task.target_aspect)
        elif model.startswith("qwen-image-edit"):
            data = qwen_image_edit(src_img, task.prompt, model=model)
        else:
            raise RuntimeError(f"unknown model {model}")
        out_path.write_bytes(data)
        elapsed = time.time() - t0
        return Result(model=model, task_id=task.id, ok=True, out_path=out_path,
                      cost_usd=PRICING_USD[model], elapsed_s=elapsed)
    except Exception as e:
        elapsed = time.time() - t0
        msg = f"{type(e).__name__}: {e}"
        print(f"  ! {model} {task.id} FAILED in {elapsed:.1f}s: {msg[:200]}")
        return Result(model=model, task_id=task.id, ok=False,
                      cost_usd=0.0, elapsed_s=elapsed, error=msg)

def write_summary(results: list[Result]) -> None:
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Image-edit benchmark — 2026-04-26\n")
    lines.append("Same prompt per task across all vendors. Sources from "
                 "`projects/olga/inputs/`. EXIF transposed before sending.\n")

    lines.append("## Tasks\n")
    for t in TASKS:
        lines.append(f"### {t.id}\n")
        lines.append(f"- Source: `projects/olga/inputs/{t.src}`")
        lines.append(f"- Outpaint: `{t.is_outpaint}` (target {t.target_aspect})")
        lines.append(f"- Prompt: {t.prompt}\n")

    lines.append("## Results\n")
    lines.append("| Task | " + " | ".join(MODELS_TO_RUN) + " |")
    lines.append("|---|" + "|".join(["---"] * len(MODELS_TO_RUN)) + "|")
    by_key = {(r.model, r.task_id): r for r in results}
    for t in TASKS:
        row = [t.id]
        for m in MODELS_TO_RUN:
            r = by_key.get((m, t.id))
            if r is None:
                row.append("—")
            elif r.ok:
                rel = r.out_path.relative_to(OUT_BASE).as_posix()
                row.append(f"[![{m}]({rel})]({rel}) {r.elapsed_s:.1f}s ${r.cost_usd:.3f}")
            else:
                row.append(f"FAIL: {r.error[:100]}")
        lines.append("| " + " | ".join(row) + " |")

    total_cost = sum(r.cost_usd for r in results if r.ok)
    n_ok = sum(1 for r in results if r.ok)
    lines.append(f"\n**Totals:** {n_ok}/{len(results)} succeeded, "
                 f"actual cost ~${total_cost:.3f}")

    (OUT_BASE / "summary.md").write_text("\n".join(lines), encoding="utf-8")

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max-usd", type=float, default=2.00)
    p.add_argument("--models", default=",".join(MODELS_TO_RUN),
                   help="comma-separated subset")
    p.add_argument("--tasks", default=",".join(t.id for t in TASKS))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    task_ids = {t.strip() for t in args.tasks.split(",") if t.strip()}
    tasks = [t for t in TASKS if t.id in task_ids]

    est = estimate_total_cost(models, len(tasks))
    print(f"Cost estimate: ~${est:.3f} ({len(models)} models × {len(tasks)} tasks)")
    print(f"Cap (--max-usd): ${args.max_usd:.2f}")
    if est > args.max_usd:
        print("ABORT: estimate > cap. Re-run with --max-usd to override.")
        return 2
    if args.dry_run:
        print("Dry run. Matrix:")
        for m in models:
            for t in tasks:
                print(f"  {m} × {t.id}  ~${PRICING_USD[m]:.3f}")
        return 0

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    results: list[Result] = []
    for m in models:
        print(f"\n=== {m} ===")
        for t in tasks:
            print(f"  -> {t.id} ...", flush=True)
            r = run_one(m, t)
            if r.ok:
                print(f"     OK  {r.elapsed_s:.1f}s -> {r.out_path.relative_to(ROOT)}")
            results.append(r)

    write_summary(results)
    print(f"\nSummary: {OUT_BASE / 'summary.md'}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
