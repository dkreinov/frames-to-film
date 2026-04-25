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
| 4 | Stitch-designed React commercial UI | done | 2, 3 | 5 screens via `/stitch-design` → shadcn/ui React → FastAPI. All 6 sub-plans shipped: Upload, Prepare, Storyboard, Generate, Review+Export, Settings (Gemini key in localStorage + `X-Gemini-Key` header; per-stage mode toggles, only generatePrompts `api` enabled — rest gated to Phase 5). |
| 5 | Paid fal.ai Kling O3 video generation | done | 1, 2 | Pivoted from free Playwright/Veo to paid fal.ai Kling O3 (latest Kling 3.0 first+last-frame, $0.084/s audio-off, 5s clips). Generate api mode calls kling_fal adapter with user-supplied fal.ai key from Settings (`X-Fal-Key` header). |
| 6 | Full E2E + polish + ship | review | 4, 5 | Sub-Plans 1+2 done; CI green; legacy moved; README rewritten. Remaining `/app-design` + `/frontend-design` passes folded into Phase 7 sub-plans (since 7.4/7.5 add new UI). Vercel deploy explicitly deferred until Phase 7 quality lands — public deploy of current quality = first-impression risk. |
| 7 | Quality: story-aware pipeline + judge-driven eval | pending | 6 | Story arc parameter + brief input + story writer + cinematic devices catalog + three-tier judge stack + eval harness with AI/human calibration + stitch polish. Built for paid-service stage (operator-driven, single tenant). 8 sub-plans (7.1–7.7 + 7.5b Kling-vs-Wan-2.7 generator A/B), ~14-19 focused days. See `phase_7_overview.md` and `phase_7_plan.md`. 7.1 ✓ done. |
| 8 | SaaS readiness | pending | 7 | Auth, billing (Stripe), multi-tenant isolation, public landing, Vercel deploy. Out of scope until paid-service stage validates demand. |

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

### Phase 5 — Paid fal.ai Kling O3 video generation
- Direct fal.ai API (`Authorization: Key <FAL_KEY>`), Kling O3
  first-last-frame endpoint, 5s audio-off clips (~$0.084/s)
- Single `X-Fal-Key` header from browser-stored key (Settings)
- `backend/services/kling_fal.py` adapter replaces the legacy
  `generate_all_videos.py` JWT-based Kling path in the api branch
- Logical: 8/8 backend integration tests green with mocked HTTP
- Working: `tests/backend/test_kling_fal_real.py` smoke test passes
  against real fal.ai when `FAL_KEY` env var is set (~$0.42/run)
- General design: advisor pass (pre-close-out)

**Pivot note**: originally scoped as free Playwright-driven Veo/Kling
web automation. Sub-Plan 1 built the `'web'` Mode scaffolding, but
Veo doesn't support first+last frame (project requirement) and Grok
API lacks end-frame support entirely. Kling is the only vendor that
does it natively, and fal.ai wraps it with pay-as-you-go pricing
(no $10 minimum like official Kling). Sub-Plan 1 scaffolding reverted
in Sub-Plan 2 Step 2 (Mode narrowed back to mock/api, adapter stub
deleted).

### Phase 6 — Ship
- Full Playwright E2E in mock mode runs under CI
- Claude-in-Chrome visual smoke test recorded as GIF (`mcp__claude-in-chrome__gif_creator`)
- Deploy target: Vercel for UI; self-host backend (Playwright needs local Chrome profile for web-mode)
- `/app-design` and `/frontend-design` final pass
- Docs: README updated with commercial tool positioning; legacy Streamlit moved to `legacy/`
- General design: advisor pass
