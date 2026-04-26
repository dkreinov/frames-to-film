"""Regenerate summary.md from on-disk benchmark PNGs."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.bench_image_edit import OUT_BASE, MODELS_TO_RUN, TASKS, PRICING_USD  # noqa

GPT_NOTE = (
    "FAIL — org-verification required at "
    "platform.openai.com/settings/organization/general"
)
GEMINI_25_T2_NOTE = "FAIL — moderation block (FinishReason.IMAGE_OTHER)"

NOTES: dict[tuple[str, str], str] = {
    ("gpt-image-2-medium", t.id): GPT_NOTE for t in TASKS
}
NOTES[("gemini-2.5-flash-image", "T2_outfit_swap")] = GEMINI_25_T2_NOTE


def main() -> None:
    lines: list[str] = []
    lines.append("# Image-edit benchmark — 2026-04-26\n")
    lines.append(
        "Same prompt per task across all vendors. EXIF-transposed sources from "
        "`projects/olga/inputs/`. Outpaint tasks (T1, T3) use padded canvas + "
        "alpha mask for gpt-image-2; Gemini and Qwen accept outpaint via prompt.\n"
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
    lines.append("Click a thumbnail to view the full PNG.\n")
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
        "Visual review of the 15 generated outputs against each task brief:\n"
    )
    lines.append(
        "1. **`gemini-3-pro-image-preview` ($0.134/img) — best quality overall.** "
        "T1 extends the vintage portrait to a clean 16:9 with the warm sepia palette "
        "and organic foliage continuing past the original edges. T3 cleanly extends "
        "the wedding frame to include the full crouching man with golden-hour "
        "lighting intact and zero face drift. Recommended for outpaint / extend "
        "work where identity + color continuity is non-negotiable.\n"
    )
    lines.append(
        "2. **`gemini-3.1-flash-image-preview` ($0.067/img) — best price/quality.** "
        "Half the price of 3-pro, ~equivalent quality on T2 (clean turtleneck + "
        "trousers, B&W mood preserved) and T4 (legible handwritten note 'FIND ME "
        "AT THE OAK… THE KEY IS…' as a story-clue prop). Slight artistic license "
        "on T1 (added a curtained-wallpaper room). Recommended for high-volume "
        "instruction edits and as a default fallback.\n"
    )
    lines.append(
        "3. **`qwen-image-edit` ($0.025/img) — cheapest, but resolution-limited.** "
        "All four edits ran without moderation issues, identity and palette held "
        "up reasonably, but DashScope returned thumbnail-class outputs (256-512px) "
        "which are not usable as video keyframes without an explicit `size` / "
        "`resolution` parameter. Worth a follow-up to set higher resolution; if "
        "that works, this is the budget tier for retries and ablations.\n"
    )
    lines.append(
        "4. **`gemini-2.5-flash-image` ($0.039/img) — skip for production.** Two "
        "structural issues: (a) moderation block on the B&W glamour outfit swap "
        "(T2) where the newer 3.1-flash and 3-pro tiers handled it cleanly, and "
        "(b) outputs come back at the original input dimensions on outpaint tasks "
        "rather than the requested wider aspect. Cheap, but not the right choice "
        "for the four jobs you actually need.\n"
    )
    lines.append(
        "5. **`gpt-image-2-medium` ($0.053/img) — pending org verification.** "
        "Same script will run once the OpenAI org is verified. Worth re-testing "
        "for T1/T3 with the masked-canvas outpaint path already wired in the "
        "script, since gpt-image-2 is the only tier here with explicit mask "
        "support.\n"
    )

    lines.append("## Failure modes observed\n")
    lines.append(
        "- **gpt-image-2** — OpenAI organization verification required before any call. "
        "User must visit https://platform.openai.com/settings/organization/general and "
        "complete identity verification (~30 min for activation). After that the same "
        "script should run; cost contribution would have been ~$0.21 for 4 medium-quality "
        "edits at 1536×1024.\n"
    )
    lines.append(
        "- **gemini-2.5-flash-image** + T2 outfit swap — returned `FinishReason.IMAGE_OTHER` "
        "with empty content (silent moderation block). The 3.1-flash-image-preview and "
        "3-pro-image-preview tiers handled the same prompt. Suggests the older 2.5 has a "
        "more conservative person-in-clothing safety policy.\n"
    )
    lines.append(
        "- **qwen-image-edit** — initial async submission rejected by DashScope tier "
        "(`AccessDenied: current user api does not support asynchronous calls`). Switched "
        "to sync mode; works on the QWEEN_KEY Singapore endpoint without further changes.\n"
    )

    lines.append("## Reproducing\n")
    lines.append("```")
    lines.append("# full grid (≈$1.27 with all 5 models)")
    lines.append("python tools/bench_image_edit.py --max-usd 2.00")
    lines.append("# subset")
    lines.append(
        "python tools/bench_image_edit.py "
        "--models gemini-3-pro-image-preview,qwen-image-edit "
        "--tasks T1_extend"
    )
    lines.append("# regenerate this file")
    lines.append("python tools/bench_image_edit_summary.py")
    lines.append("```")

    out = OUT_BASE / "summary.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} — {n_ok}/{n_total} cells")


if __name__ == "__main__":
    main()
