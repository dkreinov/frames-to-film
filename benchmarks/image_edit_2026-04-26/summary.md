# Image-edit benchmark — 2026-04-26

Same prompt per task across all vendors. EXIF-transposed sources from `projects/olga/inputs/`. Outpaint tasks (T1, T3) use padded canvas + alpha mask for gpt-image-2; Gemini and Qwen accept outpaint via prompt.

## Tasks & prompts

### T1_extend (outpaint) target (16, 9)
- Source: `projects/olga/inputs/20260220_183907.jpg`
- Prompt: Extend this vintage photograph to 16:9 widescreen by widening it horizontally. Preserve the person, face, expression, hair, hair-bow, clothing, and pose exactly. Match the existing faded vintage color palette (warm sepia and red tones), film grain, and aged photographic feel. Continue the surrounding background naturally on both sides. No seams, no color shift, no new people.

### T2_outfit_swap (instruction) 
- Source: `projects/olga/inputs/1772197775009-c3667866-c93f-42ea-916e-2dc9008f9ad6.jpg`
- Prompt: Replace the dress with a tailored black turtleneck sweater and high-waisted black trousers. Keep the woman's face, hair, makeup, earrings, pose, and the studio backdrop and lighting exactly the same. Preserve the black-and-white film aesthetic and the high-fashion studio-photography mood.

### T3_recompose (outpaint) target (4, 3)
- Source: `projects/olga/inputs/5190668344_65af8357de_b.jpg`
- Prompt: Recompose this wedding photograph: the crouching man at the bottom right is partially cut off by the frame edge. Extend the bottom and right sides of the image to include him fully and cleanly. Preserve every face, expression, the bride's gown, the groom's suit, the tallit, the chuppah backdrop with string lights, and the warm golden-hour color palette. Keep all original people exactly once, no duplicates, no invented faces.

### T4_add_item (instruction) 
- Source: `projects/olga/inputs/20260227_153417.jpg`
- Prompt: Add a small folded handwritten paper note resting on the counter next to the woman, partially visible with a few words written in ink. The note should look like a clue or message for a story transition. Keep the woman, her smile, hair, striped shirt, the cafe interior, all glassware and cups, the dessert she is holding, and the existing warm window light exactly unchanged.

## Per-image price (1024² class)

| Model | $/img |
|---|---|
| `gemini-2.5-flash-image` | $0.039 |
| `gemini-3.1-flash-image-preview` | $0.067 |
| `gemini-3-pro-image-preview` | $0.134 |
| `gpt-image-2-medium` | $0.053 |
| `qwen-image-edit` | $0.025 |

## Result grid

Click a thumbnail to view the full PNG.

| Task | gemini-2.5-flash-image | gemini-3.1-flash-image-preview | gemini-3-pro-image-preview | gpt-image-2-medium | qwen-image-edit |
|---|---|---|---|---|---|
| T1_extend | [![gemini-2.5-flash-image T1_extend](gemini-2.5-flash-image/T1_extend.png)](gemini-2.5-flash-image/T1_extend.png) | [![gemini-3.1-flash-image-preview T1_extend](gemini-3.1-flash-image-preview/T1_extend.png)](gemini-3.1-flash-image-preview/T1_extend.png) | [![gemini-3-pro-image-preview T1_extend](gemini-3-pro-image-preview/T1_extend.png)](gemini-3-pro-image-preview/T1_extend.png) | FAIL — org-verification required at platform.openai.com/settings/organization/general | [![qwen-image-edit T1_extend](qwen-image-edit/T1_extend.png)](qwen-image-edit/T1_extend.png) |
| T2_outfit_swap | FAIL — moderation block (FinishReason.IMAGE_OTHER) | [![gemini-3.1-flash-image-preview T2_outfit_swap](gemini-3.1-flash-image-preview/T2_outfit_swap.png)](gemini-3.1-flash-image-preview/T2_outfit_swap.png) | [![gemini-3-pro-image-preview T2_outfit_swap](gemini-3-pro-image-preview/T2_outfit_swap.png)](gemini-3-pro-image-preview/T2_outfit_swap.png) | FAIL — org-verification required at platform.openai.com/settings/organization/general | [![qwen-image-edit T2_outfit_swap](qwen-image-edit/T2_outfit_swap.png)](qwen-image-edit/T2_outfit_swap.png) |
| T3_recompose | [![gemini-2.5-flash-image T3_recompose](gemini-2.5-flash-image/T3_recompose.png)](gemini-2.5-flash-image/T3_recompose.png) | [![gemini-3.1-flash-image-preview T3_recompose](gemini-3.1-flash-image-preview/T3_recompose.png)](gemini-3.1-flash-image-preview/T3_recompose.png) | [![gemini-3-pro-image-preview T3_recompose](gemini-3-pro-image-preview/T3_recompose.png)](gemini-3-pro-image-preview/T3_recompose.png) | FAIL — org-verification required at platform.openai.com/settings/organization/general | [![qwen-image-edit T3_recompose](qwen-image-edit/T3_recompose.png)](qwen-image-edit/T3_recompose.png) |
| T4_add_item | [![gemini-2.5-flash-image T4_add_item](gemini-2.5-flash-image/T4_add_item.png)](gemini-2.5-flash-image/T4_add_item.png) | [![gemini-3.1-flash-image-preview T4_add_item](gemini-3.1-flash-image-preview/T4_add_item.png)](gemini-3.1-flash-image-preview/T4_add_item.png) | [![gemini-3-pro-image-preview T4_add_item](gemini-3-pro-image-preview/T4_add_item.png)](gemini-3-pro-image-preview/T4_add_item.png) | FAIL — org-verification required at platform.openai.com/settings/organization/general | [![qwen-image-edit T4_add_item](qwen-image-edit/T4_add_item.png)](qwen-image-edit/T4_add_item.png) |

**Totals:** 15/20 cells generated, actual cost ~$1.021

## Verdict — production picks

Visual review of the 15 generated outputs against each task brief:

1. **`gemini-3-pro-image-preview` ($0.134/img) — best quality overall.** T1 extends the vintage portrait to a clean 16:9 with the warm sepia palette and organic foliage continuing past the original edges. T3 cleanly extends the wedding frame to include the full crouching man with golden-hour lighting intact and zero face drift. Recommended for outpaint / extend work where identity + color continuity is non-negotiable.

2. **`gemini-3.1-flash-image-preview` ($0.067/img) — best price/quality.** Half the price of 3-pro, ~equivalent quality on T2 (clean turtleneck + trousers, B&W mood preserved) and T4 (legible handwritten note 'FIND ME AT THE OAK… THE KEY IS…' as a story-clue prop). Slight artistic license on T1 (added a curtained-wallpaper room). Recommended for high-volume instruction edits and as a default fallback.

3. **`qwen-image-edit` ($0.025/img) — cheapest, but resolution-limited.** All four edits ran without moderation issues, identity and palette held up reasonably, but DashScope returned thumbnail-class outputs (256-512px) which are not usable as video keyframes without an explicit `size` / `resolution` parameter. Worth a follow-up to set higher resolution; if that works, this is the budget tier for retries and ablations.

4. **`gemini-2.5-flash-image` ($0.039/img) — skip for production.** Two structural issues: (a) moderation block on the B&W glamour outfit swap (T2) where the newer 3.1-flash and 3-pro tiers handled it cleanly, and (b) outputs come back at the original input dimensions on outpaint tasks rather than the requested wider aspect. Cheap, but not the right choice for the four jobs you actually need.

5. **`gpt-image-2-medium` ($0.053/img) — pending org verification.** Same script will run once the OpenAI org is verified. Worth re-testing for T1/T3 with the masked-canvas outpaint path already wired in the script, since gpt-image-2 is the only tier here with explicit mask support.

## Failure modes observed

- **gpt-image-2** — OpenAI organization verification required before any call. User must visit https://platform.openai.com/settings/organization/general and complete identity verification (~30 min for activation). After that the same script should run; cost contribution would have been ~$0.21 for 4 medium-quality edits at 1536×1024.

- **gemini-2.5-flash-image** + T2 outfit swap — returned `FinishReason.IMAGE_OTHER` with empty content (silent moderation block). The 3.1-flash-image-preview and 3-pro-image-preview tiers handled the same prompt. Suggests the older 2.5 has a more conservative person-in-clothing safety policy.

- **qwen-image-edit** — initial async submission rejected by DashScope tier (`AccessDenied: current user api does not support asynchronous calls`). Switched to sync mode; works on the QWEEN_KEY Singapore endpoint without further changes.

## Reproducing

```
# full grid (≈$1.27 with all 5 models)
python tools/bench_image_edit.py --max-usd 2.00
# subset
python tools/bench_image_edit.py --models gemini-3-pro-image-preview,qwen-image-edit --tasks T1_extend
# regenerate this file
python tools/bench_image_edit_summary.py
```