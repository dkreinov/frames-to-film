"""Outpaint 4 portrait sources to 16:9 horizontal landscape across all
five image-edit models. Measures whether each model actually delivers
uniform aspect output — required for Kling video gen, which needs every
input frame in the same aspect ratio.

Same prompt verbatim for every model. For gpt-image-2 the source is padded
onto a 16:9-shaped 1536x864 RGBA canvas with an alpha mask marking the new
edge regions (its native outpaint path). Gemini and Qwen receive the raw
source plus the prompt — they must outpaint via prompt alone.

Output: benchmarks/normalize_16x9_2026-04-26/{model}/{src}.png
Summary: benchmarks/normalize_16x9_2026-04-26/summary.md
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.bench_image_edit import (  # noqa: E402
    PRICING_USD,
    SOURCES_DIR,
    gemini_edit,
    img_to_compact_bytes,
    img_to_png_bytes,
    load_source_canonical,
    qwen_image_edit,
)

OUT_BASE = ROOT / "benchmarks" / "normalize_16x9_2026-04-26"

SOURCES = [
    "20260220_183907.jpg",
    "1772197775009-c3667866-c93f-42ea-916e-2dc9008f9ad6.jpg",
    "5190668344_65af8357de_b.jpg",
    "20260227_153417.jpg",
]

NORMALIZE_PROMPT = (
    "Extend this photograph to a 16:9 horizontal landscape aspect ratio by "
    "widening it on both sides. Preserve every person's face, expression, "
    "hair, clothing, jewelry, and pose exactly — do not change any person. "
    "Continue the existing background naturally on the left and right. "
    "Match the current color palette, lighting, film grain, and photographic "
    "style. No seams, no color shift, no new people, no duplicate faces, "
    "no cropping of the original subject."
)

MODELS = [
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
    "gpt-image-2-medium",
    "qwen-image-edit-plus",
    "qwen-image-edit-max",
]


def gpt_outpaint_16x9(src_img: Image.Image, prompt: str) -> bytes:
    """gpt-image-2 with masked-canvas outpaint to 16:9.

    Pads the source onto a 1536x1024 canvas (closest landscape size gpt-image-2
    supports — 3:2 aspect). The alpha mask marks the side regions as the edit
    area. Result is 1536x1024, which is 3:2 (1.500), not exactly 16:9 (1.778),
    but it is the closest gpt-image-2 supports and downstream resize to 16:9
    is trivial."""
    import os, base64
    from openai import OpenAI

    key = os.environ.get("GPT_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("GPT_KEY not set")
    client = OpenAI(api_key=key)

    target_w, target_h = 1536, 1024
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    sw, sh = src_img.size
    scale = target_h / sh
    new_w = int(round(sw * scale))
    if new_w >= target_w:
        scale = target_w / sw
        new_w = target_w
        new_h = int(round(sh * scale))
    else:
        new_h = target_h
    resized = src_img.convert("RGBA").resize((new_w, new_h), Image.LANCZOS)
    off_x = (target_w - new_w) // 2
    off_y = (target_h - new_h) // 2
    canvas.paste(resized, (off_x, off_y), resized)

    mask_alpha = Image.new("L", (target_w, target_h), 0)
    keep = Image.new("L", (new_w, new_h), 255)
    mask_alpha.paste(keep, (off_x, off_y))
    mask_rgba = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    mask_rgba.putalpha(mask_alpha)

    img_bytes = img_to_png_bytes(canvas)
    mask_bytes = img_to_png_bytes(mask_rgba)
    result = client.images.edit(
        model="gpt-image-2",
        image=("source.png", img_bytes, "image/png"),
        mask=("mask.png", mask_bytes, "image/png"),
        prompt=prompt,
        size=f"{target_w}x{target_h}",
        quality="medium",
    )
    return base64.b64decode(result.data[0].b64_json)


def run(model: str, src_name: str) -> tuple[bool, Path | None, float, str]:
    out_dir = OUT_BASE / model
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = src_name.replace(" ", "_").rsplit(".", 1)[0]
    out_path = out_dir / f"{stem}.png"
    src_img = load_source_canonical(src_name)
    t0 = time.time()
    try:
        if model.startswith("gemini-"):
            data = gemini_edit(model, src_img, NORMALIZE_PROMPT)
        elif model == "gpt-image-2-medium":
            data = gpt_outpaint_16x9(src_img, NORMALIZE_PROMPT)
        elif model.startswith("qwen-image-edit"):
            data = qwen_image_edit(src_img, NORMALIZE_PROMPT, model=model)
        else:
            raise RuntimeError(f"unknown model {model}")
        out_path.write_bytes(data)
        return True, out_path, time.time() - t0, ""
    except Exception as e:
        return False, None, time.time() - t0, f"{type(e).__name__}: {str(e)[:200]}"


def measure(out_path: Path) -> tuple[int, int, float]:
    im = Image.open(out_path)
    w, h = im.size
    return w, h, w / h


def write_summary(rows: list[dict]) -> None:
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Normalize-to-16:9 benchmark — 2026-04-26\n")
    lines.append(
        "Same prompt across all five vendors. The four production sources "
        "(all portrait, aspect 0.51–0.75) must outpaint to 16:9 (1.778) "
        "horizontal landscape — required so every Kling input frame is the "
        "same shape.\n"
    )
    lines.append(f"Prompt:\n```\n{NORMALIZE_PROMPT}\n```\n")
    lines.append("## Result grid (achieved width × height, aspect, drift from 16:9)\n")
    header = "| Source | " + " | ".join(MODELS) + " |"
    lines.append(header)
    lines.append("|---" * (1 + len(MODELS)) + "|")
    for src in SOURCES:
        cells: list[str] = [f"`{src}`"]
        for m in MODELS:
            row = next(
                (r for r in rows if r["model"] == m and r["src"] == src), None
            )
            if row is None or not row["ok"]:
                cells.append(f"FAIL: {row['err'][:60] if row else 'missing'}")
                continue
            w, h, aspect = row["w"], row["h"], row["aspect"]
            drift = abs(aspect - 16 / 9) / (16 / 9)
            cells.append(
                f"![]({m}/{Path(row['out']).name}) {w}×{h} ({aspect:.2f}, "
                f"{drift*100:.0f}% off)"
            )
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(
        "**Aspect interpretation.** 16:9 = 1.778. Drift % = how far the "
        "model's output is from true 16:9. 0% = exact 16:9. A model that "
        "ignored the prompt and returned the source aspect would show ~58% "
        "drift on the tall glamour shot and ~71–60% on the others.\n"
    )

    ok_count = sum(1 for r in rows if r["ok"])
    cost = sum(PRICING_USD[r["model"]] for r in rows if r["ok"])
    lines.append(f"**Totals:** {ok_count}/{len(rows)} cells, ~${cost:.3f} spent.\n")

    (OUT_BASE / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max-usd", type=float, default=2.00)
    p.add_argument("--models", default=",".join(MODELS))
    p.add_argument("--sources", default=",".join(SOURCES))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    est = sum(PRICING_USD[m] * len(sources) for m in models)
    print(f"Cost estimate: ~${est:.3f} ({len(models)} models × {len(sources)} sources)")
    if est > args.max_usd:
        print(f"ABORT: estimate > cap (${args.max_usd:.2f})")
        return 2
    if args.dry_run:
        return 0

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for m in models:
        print(f"\n=== {m} ===")
        for s in sources:
            print(f"  -> {s} ...", flush=True)
            ok, out, elapsed, err = run(m, s)
            row = {
                "model": m,
                "src": s,
                "ok": ok,
                "out": str(out) if out else "",
                "elapsed": elapsed,
                "err": err,
            }
            if ok:
                w, h, aspect = measure(out)
                row.update(w=w, h=h, aspect=aspect)
                print(f"     OK  {elapsed:.1f}s  {w}×{h} aspect {aspect:.2f}")
            else:
                print(f"     FAIL {elapsed:.1f}s  {err[:120]}")
            rows.append(row)

    write_summary(rows)
    print(f"\nSummary: {OUT_BASE / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
