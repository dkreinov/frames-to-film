# Legacy

Archived code kept out of the active product path. Not imported by the
FastAPI backend or React frontend. Not covered by CI. Kept for
reference and personal-use scripts.

## Layout

- `scripts/` — standalone Python scripts from Phase 1 (watermark / outpaint /
  Gemini Pro extension) and the pre-Phase-4 Kling-direct video generator.
- `tests/` — pytest suites covering the `scripts/` contents. Not discovered
  by the main CI `tests/backend/` run.
- `image_prep/` — pre-outpaint still-image helpers.
- `video_generation/` — earlier manual Kling generators.
- `requirements-review.txt` — Streamlit review-UI deps. Heavy
  (ultralytics, facenet-pytorch). Install only if running the legacy
  Streamlit app.

## What moved out in Phase 6 Sub-Plan 2

| File | Previous home | Replaced by |
|---|---|---|
| `review_app.py` | repo root | React frontend (`frontend/src/routes/ReviewScreen.tsx`) |
| `review_models.py`, `review_store.py` | repo root | FastAPI `backend/services/segments.py` |
| `redo_runner.py` | repo root | The Review UI's per-segment "Redo" verdict |
| `extend_image_judge.py` | repo root | Phase 3 automated prompts (`backend/services/prompts.py`) |
| `gemini_pro_extend.py` | repo root | `backend/services/prepare.py` + user-supplied extend path |
| `outpaint_images.py`, `outpaint_16_9.py` | repo root | `backend/services/prepare.py` mock-mode stub |
| `watermark_clean.py` | repo root | Integrated into Phase 1 pipeline (deferred) |
| `image_pair_prompts.py` | repo root | Per-project `prompts.json` |
| `generate_all_videos.py` | repo root | `backend/services/kling_fal.py` (fal.ai wrapper) |
| `test_script_*.py` | `tests/backend/` | — tests for the legacy scripts |
| `test_watermark_*.py`, `test_review_app_ui.py` | `tests/` | — tests for the legacy scripts |

## Running legacy tests

From the repo root, on-demand only:

```
pytest legacy/tests -v
```

CI does not run these (workflow targets `tests/backend/` specifically).
