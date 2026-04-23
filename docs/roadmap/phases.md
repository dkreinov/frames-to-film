# Roadmap — Phases

Each phase gets its own saved plan at `docs/roadmap/phase_<N>_plan.md` (created via the `/plan` skill when that phase starts) and its own execution log at `docs/roadmap/phase_<N>_execution.md` (filled in during work).

**Iteration rule:** at the end of each phase, before starting the next, re-open the next phase's plan and update it with findings from the phase that just finished. Findings get recorded in the current phase's `_execution.md` first, then folded into the next phase's `_plan.md`.

## Status legend

- `pending` — not started
- `planning` — `/plan` in progress, plan not finalized
- `in-progress` — plan approved, execution underway
- `review` — execution done, awaiting testing gates
- `done` — all four testing gates passed (logical + general design + app design if UI + working)

## Phase table

| # | Name | Status | Depends on | Scope one-liner |
|---|---|---|---|---|
| 1 | Gemini watermark cleaner integration | done | — | Wire `gemini-watermark.exe` into every Gemini output (API + web paths). |
| 2 | FastAPI engine + mock mode + project isolation | done | 1 | Wrap scripts in HTTP API. Add `GENERATION_MODE=api\|web\|mock`. Per-project state. |
| 3 | De-Olga prompt library | done | 2 | Replace hardcoded `PAIR_PROMPTS` with per-project JSON auto-generated from image pairs. Style presets. |
| 4 | Stitch-designed React commercial UI | in-progress | 2, 3 | 5 screens via `/stitch-design` → shadcn/ui React → FastAPI. Sub-plan 1 (Upload) done; 4 remaining. |
| 5 | Free web-mode video generation | pending | 1, 2 | Playwright adapter for Veo (Gemini Pro web) or Minimax. |
| 6 | Full E2E + polish + ship | pending | 4, 5 | Playwright E2E in mock mode, Claude-in-Chrome smoke, deploy. |

## Exit criteria per phase

### Phase 1 — Watermark cleaner integration
- `outpaint_images.py`, `outpaint_16_9.py`, `gemini_pro_extend.py` all route outputs through `gemini-watermark.exe`
- `.env` toggle `WATERMARK_CLEAN=auto|off` (default auto)
- Logical: pixel diff on a known watermarked sample proves watermark region changed
- Working: 3 real images from `Olia_continue/extend_api/` visually inspected — watermark gone, faces intact
- General design: advisor pass

### Phase 2 — FastAPI engine + mock mode + isolation
- `app/api.py` or `backend/` exposing endpoints from research doc
- Per-project folder `pipeline_runs/<project_id>/` with isolated state files
- `GENERATION_MODE=mock` serves fixtures from `tests/fixtures/` (seeded from existing 78 real segments)
- Logical: pytest green against all endpoints in mock mode
- Working: curl-level smoke test: create project → upload → prepare → generate → stitch → download
- General design: advisor pass

### Phase 3 — De-Olga prompt library
- `PAIR_PROMPTS` removed (or kept only as style-preset fallback)
- Per-project `prompts.json` written by an LLM pass that looks at each image pair
- Style presets in code: `cinematic`, `nostalgic`, `vintage`, `playful`
- Logical: prompt generation on 3 unrelated photo sets, assert no Olga-specific strings ("Olga", "childhood B&W studio", etc.) leak
- Working: generate prompts for one non-Olga test project, human spot-check
- General design: advisor pass

### Phase 4 — Stitch-designed React UI
- 5 screens rendered: Upload, Prepare, Storyboard, Generate, Review+Export
- Drag-drop storyboard using `@dnd-kit`
- Settings screen for user API keys (localStorage, not server)
- Logical: Playwright E2E in mock mode hits each screen successfully
- App design: `/app-design` pass on each screen
- Frontend design: `/frontend-design` pass
- Working: Claude-in-Chrome takes golden screenshots per step
- General design: advisor pass

### Phase 5 — Free web-mode video generation
- Playwright adapter that drives Veo (via Gemini Pro web) or Minimax free tier
- Reuses `.gemini_chrome_profile/` pattern
- Watermark cleaner from Phase 1 is applied to any image frames produced
- Logical: generate 3 clips via web path, compare file size/duration to API-mode baseline
- Working: one full movie generated in web mode on a 5-photo test project
- General design: advisor pass

### Phase 6 — Ship
- Full Playwright E2E in mock mode runs under CI
- Claude-in-Chrome visual smoke test recorded as GIF (`mcp__claude-in-chrome__gif_creator`)
- Deploy target: Vercel for UI; self-host backend (Playwright needs local Chrome profile for web-mode)
- `/app-design` and `/frontend-design` final pass
- Docs: README updated with commercial tool positioning; legacy Streamlit moved to `legacy/`
- General design: advisor pass
