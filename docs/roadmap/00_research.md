# Phase 0 — Research & Baseline

**Date:** 2026-04-23
**Status:** Complete
**Owner:** kredennis@gmail.com

## What the repo is today

A personal photos → AI movie pipeline that already shipped once (a 10:25 master of Olga's life story at `kling_test/videos/full_movie_best_with_music.mp4`, 906 MB, with a 3-track music mix).

Core is file-based, script-driven, idempotent:

| Stage | Script | Input | Output |
|---|---|---|---|
| 1. Source archive | — | root `*.jpg` | raw photos |
| 2. 4:3 normalize | `outpaint_images.py` (Gemini API) | root images | `outpainted/*.jpg` |
| 3. 16:9 extend | `outpaint_16_9.py` (Gemini API) | `outpainted/` | `kling_test/*.jpg` |
| 4. Video pairs | `generate_all_videos.py` (Kling API) + `image_pair_prompts.py` | `kling_test/` | `kling_test/videos/seg_*.mp4` |
| 5. Review / retry | `review_app.py` (Streamlit) + `redo_runner.py` (Kling + Gemini rewrite) | segments | `pipeline_runs/<run_id>/{reviews,redo_queue,winners}.json` |
| 6. Stitch | `concat_videos.py` (ffmpeg stream copy) | approved segs | `full_movie.mp4` |

State under `pipeline_runs/<run_id>/*.json`. Four Kling keys rotate via `KLING_ACTIVE` in `.env`. Custom drag-drop storyboard at `components/storyboard/index.html`.

## Existing cheap / free paths (important)

- **`gemini_pro_extend.py`** — Playwright + persistent Chrome profile (`.gemini_chrome_profile/`) drives Gemini web for *free* image extension. Log in once, batch thereafter.
- **`extend_image_judge.py`** — local facenet-pytorch + YOLO judge, zero API cost. Labels each extended image `Good / Review / Bad`.
- **`tools/ffmpeg.exe`** — local ffmpeg. Stitch is stream-copy, no re-encode, zero cost.
- **`D:\Programming\claude\watermark-env\Scripts\gemini-watermark.exe`** — CLI that removes Gemini watermarks via reverse alpha blending. CLI: `gemini-watermark -i IN -o OUT`, also supports batch directory mode. Will be wired in Phase 1.

## Blockers to "real tool for other users"

1. **Streamlit monolith** — `review_app.py` is 5034 LOC, single file. Works, but UX is dev-tool (paths, folders, JSON state surfaced). Not shippable as commercial product.
2. **Hardcoded Olga-specific prompts** — 42 pairs in `image_pair_prompts.py` describing Olga's life ("childhood B&W studio", "winter snow outing"). Must be generic or LLM-generated from image content for other users.
3. **`.env`-editing onboarding** — Kling / Gemini / PROMPT_LLM keys user-supplied by hand. No settings screen.
4. **Windows-only quirks** — tkinter folder picker, hardcoded `C:\Users\nishtiak\...` interpreter paths in docs, bundled `tools/ffmpeg.exe`.
5. **No project isolation** — single `DEFAULT_RUN_ID = "local-review-run"`. All users would share state.
6. **Cost** — ~$30–50 per 10-min movie on Kling v3 ($0.35–0.50 per 8s clip × 60–80 clips).
7. **Tests stale** — `tests/test_review_app_ui.py` asserts the old 4-tab labels ("1. Extend stills"…); recent 5-step wizard refactor broke them.

## Cost map

| Call | Unit cost | Free alternative |
|---|---|---|
| Kling v3 image→video, 8s | ~$0.35–0.50 per clip | Playwright-driven Veo via Gemini Pro web or Minimax free tier |
| Gemini image edit (extend) | ~$0.01 per image | Playwright-driven Gemini web (already working via `gemini_pro_extend.py`) |
| Gemini prompt rewrite | pennies | — (keep) |
| ffmpeg concat | free | — |
| Local NN judge | free | — |

## Guiding principles going forward

- **Keep the engine** — Python scripts work and are idempotent. Wrap them, don't rewrite.
- **Introduce `GENERATION_MODE=api|web|mock`** — single knob for cost. Mock mode replays 78 existing real segments as fixtures for zero-cost E2E.
- **React UI in front, not replacing Streamlit immediately** — ship new surface; retire Streamlit when React reaches parity.
- **Watermark cleaner is universal** — every Gemini output (API or web) passes through it before save.
- **De-Olga the prompts** — per-project prompt JSON, auto-generated from image pairs.
- **Design: overdo it** — Stitch generates screens → shadcn/ui React → Claude-in-Chrome visual smoke test → `/app-design` and `/frontend-design` review gates.

## Phase list (high-level)

See `phases.md` for full phase table. Order:

1. Gemini watermark cleaner integration
2. FastAPI engine + mock mode + project isolation
3. De-Olga prompt library
4. Stitch-designed React commercial UI
5. Free web-mode video generation (Veo/Minimax via Playwright)
6. Full E2E + polish + ship

## Testing contract

See `testing_framework.md`. Every phase must pass:

- **Logical** — unit/integration/script tests, pytest where applicable
- **General design** — advisor review of architecture before declaring done
- **App design** — `/app-design` skill on UI-touching phases
- **Working** — manual or Playwright E2E on real inputs
