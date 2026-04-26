"""Regenerate summary.md from on-disk benchmark PNGs."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.bench_image_edit import OUT_BASE, MODELS_TO_RUN, TASKS, PRICING_USD  # noqa

NOTES: dict[tuple[str, str], str] = {
    ("gemini-2.5-flash-image", "T2_outfit_swap"):
        "FAIL — moderation block (FinishReason.IMAGE_OTHER)",
}


def main() -> None:
    lines: list[str] = []
    lines.append("# Image-edit benchmark — 2026-04-26\n")
    lines.append(
        "Same prompt per task across all vendors. EXIF-transposed sources "
        "from `projects/olga/inputs/`. Outpaint tasks (T1, T3) use a padded "
        "RGBA canvas + alpha mask for `gpt-image-2`; Gemini and Qwen handle "
        "outpaint via prompt only (no mask channel).\n"
    )

    lines.append("## Tasks & prompts\n")
    for t in TASKS:
        outp = "outpaint" if t.is_outpaint else "instruction"
        ar = f"target {t.target_aspect}" if t.target_aspect else ""
        lines.append(f"### {t.id} ({outp}) {ar}")
        lines.append(f"- Source: `projects/olga/inputs/{t.src}`")
        lines.append(f"- Prompt: {t.prompt}\n")

    lines.append("## Per-image price (1024² class)\n")
    lines.append("| Model | $/img |")
    lines.append("|---|---|")
    for m in MODELS_TO_RUN:
        lines.append(f"| `{m}` | ${PRICING_USD[m]:.3f} |")
    lines.append("")

    lines.append("## Result grid\n")
    lines.append("Click a thumbnail for the full PNG.\n")
    header = "| Task | " + " | ".join(MODELS_TO_RUN) + " |"
    sep = "|---|" + "|".join(["---"] * len(MODELS_TO_RUN)) + "|"
    lines.append(header)
    lines.append(sep)
    actual_cost = 0.0
    n_ok = 0
    n_total = 0
    for t in TASKS:
        row = [t.id]
        for m in MODELS_TO_RUN:
            n_total += 1
            note = NOTES.get((m, t.id))
            if note:
                row.append(note)
                continue
            png = OUT_BASE / m / f"{t.id}.png"
            if png.exists():
                rel = png.relative_to(OUT_BASE).as_posix()
                row.append(f"[![{m} {t.id}]({rel})]({rel})")
                actual_cost += PRICING_USD[m]
                n_ok += 1
            else:
                row.append("missing")
        lines.append("| " + " | ".join(row) + " |")

    lines.append(
        f"\n**Totals:** {n_ok}/{n_total} cells generated, "
        f"actual cost ~${actual_cost:.3f}\n"
    )

    lines.append("## Verdict — production picks\n")
    lines.append(
        "Visual review of every output against each task brief, ordered by "
        "production fit:\n"
    )
    lines.append(
        "1. **`gpt-image-2-medium` ($0.053/img) — overall leader.** Once OpenAI "
        "org verification clears, this beats every other model on the high-stakes "
        "tasks: T3 recompose extends the wedding frame to include the full "
        "crouching man with golden-hour lighting and faces intact (best of all "
        "seven), T2 outfit swap is the cleanest turtleneck+trousers render, T4 "
        "produces a cleanly written legible paper note in-scene, T1 extends to "
        "landscape with vintage palette held. The masked-canvas outpaint path "
        "(padded RGBA + alpha mask) is the differentiator — only OpenAI accepts "
        "an explicit mask, and it shows. Per-movie cost at 6 frames = $0.32.\n"
    )
    lines.append(
        "2. **`gemini-3-pro-image-preview` ($0.134/img) — best Gemini, premium tier.** "
        "Strongest at vintage-color preservation on T1 outpaint and clean "
        "outfit/identity work on T2. Loses to gpt-image-2 on T3 (no mask path; "
        "must rely on prompt to outpaint, which sometimes returns the original "
        "crop) and on T4 text rendering (mirrored handwriting). 2.5× the price "
        "of gpt-image-2. Use when OpenAI is not an option or for the highest-"
        "stakes hero frame.\n"
    )
    lines.append(
        "3. **`gemini-3.1-flash-image-preview` ($0.067/img) — best Gemini value.** "
        "Half the price of 3-pro, similar quality on T2/T3, and the legible "
        "handwritten note on T4 ('FIND ME AT THE OAK… THE KEY IS…') matches "
        "gpt-image-2's text-rendering quality. Slight artistic license on T1 "
        "(adds curtained-wallpaper room). Strong cost/quality default for "
        "non-outpaint instruction edits.\n"
    )
    lines.append(
        "4. **`qwen-image-edit-plus` / `qwen-image-edit-max` ($0.045 / $0.084).** "
        "Plus is the 20B Qwen-Image-Edit-2509 release; Max is the top tier. "
        "Both render the outfit swap (T2) cleanly and preserve identity well, "
        "and full-resolution output at ~896×1184 to ~1456 long-edge — usable "
        "for video keyframes. Two structural limits: (a) **neither outpaints "
        "the aspect on prompt alone** (T1 and T3 came back as the original "
        "input crop, not a wider frame), and (b) text rendering on T4 is "
        "illegible scribbles vs gpt-image-2's clean paragraph. Useful as a "
        "cheaper retry tier for instruction edits where outpaint and text "
        "are not in scope. Max barely improves on Plus for these tasks; Plus "
        "is the better cost/quality pick.\n"
    )
    lines.append(
        "5. **`qwen-image-edit` ($0.045/img) — base tier, skip in favor of Plus.** "
        "Plus is the same price for the newer 2509 model.\n"
    )
    lines.append(
        "6. **`gemini-2.5-flash-image` ($0.039/img) — drop from production.** "
        "Two structural issues: silent moderation block on T2 outfit swap "
        "(`FinishReason.IMAGE_OTHER`, while 3.1-flash and 3-pro handled the "
        "same prompt cleanly), and outputs come back at the original input "
        "dimensions on outpaint tasks rather than the requested wider aspect. "
        "Cheap, but not the right tool for the four jobs you actually need.\n"
    )

    lines.append("## Per-movie cost (6 frames, all editing on one tier)\n")
    lines.append("| Model | $/movie |")
    lines.append("|---|---|")
    for m in MODELS_TO_RUN:
        lines.append(f"| `{m}` | ${PRICING_USD[m] * 6:.2f} |")
    lines.append("")

    lines.append("## Failure modes observed\n")
    lines.append(
        "- **`gpt-image-2`** — initial run hit `403 organization must be "
        "verified` for all four tasks. After the user verified the OpenAI org, "
        "verification was intermittently propagated for the first ~5 minutes "
        "(occasional re-403 on first call to a task). Just retry. Also: the "
        "OpenAI mask must be RGBA with `alpha=0` marking the edit region — "
        "passing an L-mode grayscale mask returns "
        "`Invalid mask image format - mask size does not match image size`. "
        "Bench script now sets the alpha channel explicitly.\n"
    )
    lines.append(
        "- **`gemini-2.5-flash-image` + T2 outfit swap** — silent moderation "
        "block (`FinishReason.IMAGE_OTHER`, no content returned). The 3.1-flash "
        "and 3-pro tiers handled the same prompt without issue.\n"
    )
    lines.append(
        "- **DashScope `qwen-image-edit*`** — initial async submission rejected "
        "with `AccessDenied: current user api does not support asynchronous "
        "calls`. Switched to sync mode. The 10MB request limit also bites if "
        "the source is encoded as raw PNG — the script now resizes to 2048px "
        "long-edge + JPEG q=92 before encoding, which keeps requests <2MB.\n"
    )
    lines.append(
        "- **`wan2.5-image-edit` / `wan2.7-image-edit`** — `Model not exist` "
        "on the Singapore endpoint with the QWEEN_KEY tier. Dropped from the "
        "bench. The Qwen-branded edit models (`qwen-image-edit*`) cover the "
        "same ground.\n"
    )

    lines.append("## Reproducing\n")
    lines.append("```")
    lines.append("# full grid (≈$1.65 with all 7 models)")
    lines.append("python tools/bench_image_edit.py --max-usd 2.00")
    lines.append("# subset")
    lines.append(
        "python tools/bench_image_edit.py "
        "--models gpt-image-2-medium,qwen-image-edit-plus "
        "--tasks T1_extend"
    )
    lines.append("# regenerate this file")
    lines.append("python tools/bench_image_edit_summary.py")
    lines.append("```")

    out = OUT_BASE / "summary.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} - {n_ok}/{n_total} cells")


if __name__ == "__main__":
    main()
