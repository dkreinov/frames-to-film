# Image-edit benchmark — 2026-04-26

Same prompt per task across all vendors. EXIF-transposed sources from `projects/olga/inputs/`. Outpaint tasks (T1, T3) use a padded RGBA canvas + alpha mask for `gpt-image-2`; Gemini and Qwen handle outpaint via prompt only (no mask channel).

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
| `qwen-image-edit` | $0.045 |
| `qwen-image-edit-plus` | $0.045 |
| `qwen-image-edit-max` | $0.084 |

## Result grid

Click a thumbnail for the full PNG.

| Task | gemini-2.5-flash-image | gemini-3.1-flash-image-preview | gemini-3-pro-image-preview | gpt-image-2-medium | qwen-image-edit | qwen-image-edit-plus | qwen-image-edit-max |
|---|---|---|---|---|---|---|---|
| T1_extend | [![gemini-2.5-flash-image T1_extend](gemini-2.5-flash-image/T1_extend.png)](gemini-2.5-flash-image/T1_extend.png) | [![gemini-3.1-flash-image-preview T1_extend](gemini-3.1-flash-image-preview/T1_extend.png)](gemini-3.1-flash-image-preview/T1_extend.png) | [![gemini-3-pro-image-preview T1_extend](gemini-3-pro-image-preview/T1_extend.png)](gemini-3-pro-image-preview/T1_extend.png) | [![gpt-image-2-medium T1_extend](gpt-image-2-medium/T1_extend.png)](gpt-image-2-medium/T1_extend.png) | [![qwen-image-edit T1_extend](qwen-image-edit/T1_extend.png)](qwen-image-edit/T1_extend.png) | [![qwen-image-edit-plus T1_extend](qwen-image-edit-plus/T1_extend.png)](qwen-image-edit-plus/T1_extend.png) | [![qwen-image-edit-max T1_extend](qwen-image-edit-max/T1_extend.png)](qwen-image-edit-max/T1_extend.png) |
| T2_outfit_swap | FAIL — moderation block (FinishReason.IMAGE_OTHER) | [![gemini-3.1-flash-image-preview T2_outfit_swap](gemini-3.1-flash-image-preview/T2_outfit_swap.png)](gemini-3.1-flash-image-preview/T2_outfit_swap.png) | [![gemini-3-pro-image-preview T2_outfit_swap](gemini-3-pro-image-preview/T2_outfit_swap.png)](gemini-3-pro-image-preview/T2_outfit_swap.png) | [![gpt-image-2-medium T2_outfit_swap](gpt-image-2-medium/T2_outfit_swap.png)](gpt-image-2-medium/T2_outfit_swap.png) | [![qwen-image-edit T2_outfit_swap](qwen-image-edit/T2_outfit_swap.png)](qwen-image-edit/T2_outfit_swap.png) | [![qwen-image-edit-plus T2_outfit_swap](qwen-image-edit-plus/T2_outfit_swap.png)](qwen-image-edit-plus/T2_outfit_swap.png) | [![qwen-image-edit-max T2_outfit_swap](qwen-image-edit-max/T2_outfit_swap.png)](qwen-image-edit-max/T2_outfit_swap.png) |
| T3_recompose | [![gemini-2.5-flash-image T3_recompose](gemini-2.5-flash-image/T3_recompose.png)](gemini-2.5-flash-image/T3_recompose.png) | [![gemini-3.1-flash-image-preview T3_recompose](gemini-3.1-flash-image-preview/T3_recompose.png)](gemini-3.1-flash-image-preview/T3_recompose.png) | [![gemini-3-pro-image-preview T3_recompose](gemini-3-pro-image-preview/T3_recompose.png)](gemini-3-pro-image-preview/T3_recompose.png) | [![gpt-image-2-medium T3_recompose](gpt-image-2-medium/T3_recompose.png)](gpt-image-2-medium/T3_recompose.png) | [![qwen-image-edit T3_recompose](qwen-image-edit/T3_recompose.png)](qwen-image-edit/T3_recompose.png) | [![qwen-image-edit-plus T3_recompose](qwen-image-edit-plus/T3_recompose.png)](qwen-image-edit-plus/T3_recompose.png) | [![qwen-image-edit-max T3_recompose](qwen-image-edit-max/T3_recompose.png)](qwen-image-edit-max/T3_recompose.png) |
| T4_add_item | [![gemini-2.5-flash-image T4_add_item](gemini-2.5-flash-image/T4_add_item.png)](gemini-2.5-flash-image/T4_add_item.png) | [![gemini-3.1-flash-image-preview T4_add_item](gemini-3.1-flash-image-preview/T4_add_item.png)](gemini-3.1-flash-image-preview/T4_add_item.png) | [![gemini-3-pro-image-preview T4_add_item](gemini-3-pro-image-preview/T4_add_item.png)](gemini-3-pro-image-preview/T4_add_item.png) | [![gpt-image-2-medium T4_add_item](gpt-image-2-medium/T4_add_item.png)](gpt-image-2-medium/T4_add_item.png) | [![qwen-image-edit T4_add_item](qwen-image-edit/T4_add_item.png)](qwen-image-edit/T4_add_item.png) | [![qwen-image-edit-plus T4_add_item](qwen-image-edit-plus/T4_add_item.png)](qwen-image-edit-plus/T4_add_item.png) | [![qwen-image-edit-max T4_add_item](qwen-image-edit-max/T4_add_item.png)](qwen-image-edit-max/T4_add_item.png) |

**Totals:** 27/28 cells generated, actual cost ~$1.829

## Verdict — production picks

Visual review of every output against each task brief, ordered by production fit:

1. **`gpt-image-2-medium` ($0.053/img) — overall leader.** Once OpenAI org verification clears, this beats every other model on the high-stakes tasks: T3 recompose extends the wedding frame to include the full crouching man with golden-hour lighting and faces intact (best of all seven), T2 outfit swap is the cleanest turtleneck+trousers render, T4 produces a cleanly written legible paper note in-scene, T1 extends to landscape with vintage palette held. The masked-canvas outpaint path (padded RGBA + alpha mask) is the differentiator — only OpenAI accepts an explicit mask, and it shows. Per-movie cost at 6 frames = $0.32.

2. **`gemini-3-pro-image-preview` ($0.134/img) — best Gemini, premium tier.** Strongest at vintage-color preservation on T1 outpaint and clean outfit/identity work on T2. Loses to gpt-image-2 on T3 (no mask path; must rely on prompt to outpaint, which sometimes returns the original crop) and on T4 text rendering (mirrored handwriting). 2.5× the price of gpt-image-2. Use when OpenAI is not an option or for the highest-stakes hero frame.

3. **`gemini-3.1-flash-image-preview` ($0.067/img) — best Gemini value.** Half the price of 3-pro, similar quality on T2/T3, and the legible handwritten note on T4 ('FIND ME AT THE OAK… THE KEY IS…') matches gpt-image-2's text-rendering quality. Slight artistic license on T1 (adds curtained-wallpaper room). Strong cost/quality default for non-outpaint instruction edits.

4. **`qwen-image-edit-plus` / `qwen-image-edit-max` ($0.045 / $0.084).** Plus is the 20B Qwen-Image-Edit-2509 release; Max is the top tier. Both render the outfit swap (T2) cleanly and preserve identity well, and full-resolution output at ~896×1184 to ~1456 long-edge — usable for video keyframes. Two structural limits: (a) **neither outpaints the aspect on prompt alone** (T1 and T3 came back as the original input crop, not a wider frame), and (b) text rendering on T4 is illegible scribbles vs gpt-image-2's clean paragraph. Useful as a cheaper retry tier for instruction edits where outpaint and text are not in scope. Max barely improves on Plus for these tasks; Plus is the better cost/quality pick.

5. **`qwen-image-edit` ($0.045/img) — base tier, skip in favor of Plus.** Plus is the same price for the newer 2509 model.

6. **`gemini-2.5-flash-image` ($0.039/img) — drop from production.** Two structural issues: silent moderation block on T2 outfit swap (`FinishReason.IMAGE_OTHER`, while 3.1-flash and 3-pro handled the same prompt cleanly), and outputs come back at the original input dimensions on outpaint tasks rather than the requested wider aspect. Cheap, but not the right tool for the four jobs you actually need.

## Per-movie cost (6 frames, all editing on one tier)

| Model | $/movie |
|---|---|
| `gemini-2.5-flash-image` | $0.23 |
| `gemini-3.1-flash-image-preview` | $0.40 |
| `gemini-3-pro-image-preview` | $0.80 |
| `gpt-image-2-medium` | $0.32 |
| `qwen-image-edit` | $0.27 |
| `qwen-image-edit-plus` | $0.27 |
| `qwen-image-edit-max` | $0.50 |

## Failure modes observed

- **`gpt-image-2`** — initial run hit `403 organization must be verified` for all four tasks. After the user verified the OpenAI org, verification was intermittently propagated for the first ~5 minutes (occasional re-403 on first call to a task). Just retry. Also: the OpenAI mask must be RGBA with `alpha=0` marking the edit region — passing an L-mode grayscale mask returns `Invalid mask image format - mask size does not match image size`. Bench script now sets the alpha channel explicitly.

- **`gemini-2.5-flash-image` + T2 outfit swap** — silent moderation block (`FinishReason.IMAGE_OTHER`, no content returned). The 3.1-flash and 3-pro tiers handled the same prompt without issue.

- **DashScope `qwen-image-edit*`** — initial async submission rejected with `AccessDenied: current user api does not support asynchronous calls`. Switched to sync mode. The 10MB request limit also bites if the source is encoded as raw PNG — the script now resizes to 2048px long-edge + JPEG q=92 before encoding, which keeps requests <2MB.

- **`wan2.5-image-edit` / `wan2.7-image-edit`** — `Model not exist` on the Singapore endpoint with the QWEEN_KEY tier. Dropped from the bench. The Qwen-branded edit models (`qwen-image-edit*`) cover the same ground.

## Reproducing

```
# full grid (≈$1.65 with all 7 models)
python tools/bench_image_edit.py --max-usd 2.00
# subset
python tools/bench_image_edit.py --models gpt-image-2-medium,qwen-image-edit-plus --tasks T1_extend
# regenerate this file
python tools/bench_image_edit_summary.py
```