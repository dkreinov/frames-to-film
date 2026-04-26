# Normalize-to-16:9 benchmark — 2026-04-26

Same prompt across all five vendors. The four production sources (all portrait, aspect 0.51–0.75) must outpaint to 16:9 (1.778) horizontal landscape — required so every Kling input frame is the same shape.

Prompt:
```
Extend this photograph to a 16:9 horizontal landscape aspect ratio by widening it on both sides. Preserve every person's face, expression, hair, clothing, jewelry, and pose exactly — do not change any person. Continue the existing background naturally on the left and right. Match the current color palette, lighting, film grain, and photographic style. No seams, no color shift, no new people, no duplicate faces, no cropping of the original subject.
```

## Result grid (achieved width × height, aspect, drift from 16:9)

| Source | gemini-3.1-flash-image-preview | gemini-3-pro-image-preview | gpt-image-2-medium | qwen-image-edit-plus | qwen-image-edit-max |
|---|---|---|---|---|---|
| `20260220_183907.jpg` | ![](gemini-3.1-flash-image-preview/20260220_183907.png) 1376×768 (1.79, 1% off) | ![](gemini-3-pro-image-preview/20260220_183907.png) 1376×768 (1.79, 1% off) | ![](gpt-image-2-medium/20260220_183907.png) 1536×1024 (1.50, 16% off) | ![](qwen-image-edit-plus/20260220_183907.png) 896×1184 (0.76, 57% off) | ![](qwen-image-edit-max/20260220_183907.png) 896×1184 (0.76, 57% off) |
| `1772197775009-c3667866-c93f-42ea-916e-2dc9008f9ad6.jpg` | ![](gemini-3.1-flash-image-preview/1772197775009-c3667866-c93f-42ea-916e-2dc9008f9ad6.png) 1376×768 (1.79, 1% off) | ![](gemini-3-pro-image-preview/1772197775009-c3667866-c93f-42ea-916e-2dc9008f9ad6.png) 1376×768 (1.79, 1% off) | FAIL: BadRequestError: Error code: 400 - {'error': {'message': 'Yo | ![](qwen-image-edit-plus/1772197775009-c3667866-c93f-42ea-916e-2dc9008f9ad6.png) 736×1440 (0.51, 71% off) | ![](qwen-image-edit-max/1772197775009-c3667866-c93f-42ea-916e-2dc9008f9ad6.png) 736×1440 (0.51, 71% off) |
| `5190668344_65af8357de_b.jpg` | ![](gemini-3.1-flash-image-preview/5190668344_65af8357de_b.png) 1376×768 (1.79, 1% off) | ![](gemini-3-pro-image-preview/5190668344_65af8357de_b.png) 1376×768 (1.79, 1% off) | ![](gpt-image-2-medium/5190668344_65af8357de_b.png) 1536×1024 (1.50, 16% off) | ![](qwen-image-edit-plus/5190668344_65af8357de_b.png) 832×1248 (0.67, 63% off) | ![](qwen-image-edit-max/5190668344_65af8357de_b.png) 832×1248 (0.67, 63% off) |
| `20260227_153417.jpg` | ![](gemini-3.1-flash-image-preview/20260227_153417.png) 1376×768 (1.79, 1% off) | ![](gemini-3-pro-image-preview/20260227_153417.png) 1376×768 (1.79, 1% off) | ![](gpt-image-2-medium/20260227_153417.png) 1536×1024 (1.50, 16% off) | ![](qwen-image-edit-plus/20260227_153417.png) 896×1184 (0.76, 57% off) | ![](qwen-image-edit-max/20260227_153417.png) 896×1184 (0.76, 57% off) |

**Aspect interpretation.** 16:9 = 1.778. Drift % = how far the model's output is from true 16:9. 0% = exact 16:9. A model that ignored the prompt and returned the source aspect would show ~58% drift on the tall glamour shot and ~71–60% on the others.

**Totals:** 19/20 cells, ~$1.479 spent.
