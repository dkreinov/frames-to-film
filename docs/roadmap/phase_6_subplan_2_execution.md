# Phase 6 — Sub-Plan 2 Execution Log (push + CI verify + legacy move)

**Sub-plan:** 2 of N.
**Status:** done
**Plan:** `plans/plan-20260424-1832.md` (self-deleted on close-out)
**Date:** 2026-04-24

## Outcome

First actual CI runs on GitHub (4 attempts total). The newly-introduced
`.github/workflows/test.yml` surfaced five concrete Linux-vs-Windows
gaps that had never been exercised — all fixed. Then moved 11 legacy
Python scripts + 7 legacy tests into `legacy/` to keep the active
repo surface clean, and confirmed CI stays green on the reduced set.

- Final CI run 24902163402: backend pytest 105 passed + 2 skipped,
  frontend vitest 93 passed + tsc clean, Playwright E2E 14 passed.
- 5 fix commits on top of the original 103 (push #1 red → 5a92bf7 green).

## What the first CI run exposed

| # | Commit | Problem | Root cause | Fix |
|---|---|---|---|---|
| 1 | 4616784 | backend: `ModuleNotFoundError: No module named 'PIL'` | `backend/services/prepare.py` imports Pillow; never declared in `requirements.txt` (local env had it transitively) | added `Pillow>=10.0` |
| 2 | 4616784 | frontend: `npm ci` — "Missing: @emnapi/core@1.10.0 from lock file" | peer deps of `@napi-rs/wasm-runtime` declared but not resolved in lock's `packages{}` map | `rm package-lock.json && npm install` + `--save-peer` |
| 3 | 3415839 | backend: 4 failures in `test_script_*.py` — `No module named 'google'` | Legacy Phase-1 outpaint scripts `import google.genai`; not declared | added `google-genai` (provisional; removed in Step 5 after tests moved to legacy/) |
| 4 | 3415839 | E2E: 13/14 `setInputFiles` 30s timeouts | `npm run dev` Vite compiles on-demand; first cold request on CI exceeds the default test timeout | CI-only switch to `npm run build && vite preview`; test timeout 30s → 90s |
| 5 | cbc6b0d | E2E: `vite build` error "Cannot resolve entry module index.html" | root `.gitignore` rule `*.html` silently untracked Vite's `frontend/index.html` — existed locally, never pushed | added `!frontend/index.html` negation + `git add` |

## Frozen contracts introduced

- **`Pillow` is a hard backend dep** — declared in `requirements.txt`.
  Any future image-processing backend service can rely on it.
- **CI uses `vite preview`, local dev uses `vite`** — `playwright.config.ts`
  branches on `process.env.CI`. If CI tests flake again, the first
  suspect is Vite preview startup timing, not HMR.
- **`frontend/index.html` is explicitly tracked** — `.gitignore` has
  a per-file negation. Any future HTML entry points need the same.
- **Backend api-mode prepare/extend raises `NotImplementedError`** —
  the Phase-1 outpaint scripts moved to `legacy/scripts/`; the api
  branches can't lazy-import them anymore. Settings UI gates the
  radios disabled; the NotImplementedError is the safety net if
  someone bypasses the UI.
- **`legacy/` is CI-excluded by path** — the GitHub Actions workflow
  runs `pytest tests/backend -v` (not `pytest` from repo root). Any
  future CI-skipped code lives under `legacy/`.

## Decisions made during execution

- **`gh auth login` once up-front** — saved 3 blind-fix cycles.
  Without CI logs, every CI failure would have been a guess.
- **Fix CI green BEFORE moving legacy** — the alternative (move
  first, then push) would have conflated 5 CI fixes with the legacy
  refactor in the same diff. Separating the concerns kept each
  commit's intent clear.
- **Replace lazy imports with `NotImplementedError`, not `legacy.scripts.*`** —
  the api-mode paths for prepare/extend were never productized; the
  Settings UI keeps them disabled. A clear not-implemented error
  matches the UI state. If api mode later becomes real for those
  stages, they'll need a new implementation anyway — not a reach
  into legacy code.
- **Keep `concat_videos.py` at root** — it's the only legacy-era
  script still imported by the active backend (`backend/services/stitch.py`).
  Moving it would require refactoring stitch.py first; deferred.
- **Remove `google-genai` from requirements in Step 5** — the only
  consumers (test_script_*.py) moved to legacy/tests/ in Step 4.
  Keeping the dep in the active install would have added ~100MB of
  Google AI deps for nothing. Kept it provisional through Step 4 so
  CI stayed green mid-transition.
- **Don't mark Phase 6 task complete** — this sub-plan only covered
  push + CI verify + legacy move. README rewrite, design passes,
  and deploy remain. Task #6 stays in-progress.

## Adjustments from the plan

- Steps 4+5 were pushed as separate commits but monitored under one
  CI run for speed. Safe because Step 4 (moves) left active tests
  passing; Step 5 (residual imports) was the cleanup that made the
  active tree truly free of the moved module names.
- The plan expected 2 push cycles. Real count was 4 CI runs (5
  commits) because the first CI run surfaced stacked issues that
  could only be diagnosed in sequence once `gh` auth was available.

## Files touched (this sub-plan)

### Root / config
- `requirements.txt` — `Pillow>=10.0`; `google-genai` added then removed.
- `.gitignore` — `!frontend/index.html` negation.
- `frontend/index.html` — newly tracked (was gitignored).
- `frontend/package-lock.json` — regenerated from scratch.
- `frontend/package.json` — `@emnapi/core` + `@emnapi/runtime` as peer deps.
- `frontend/playwright.config.ts` — CI-aware webServer + 90s test timeout.

### Backend (residual import cleanup)
- `backend/services/prepare.py` — api branch → NotImplementedError.
- `backend/services/extend.py` — api branch → NotImplementedError.
- `backend/services/prompts.py` — stale docstring reference removed.

### Legacy move
- 11 scripts moved repo-root → `legacy/scripts/` (review_app,
  review_models, review_store, redo_runner, extend_image_judge,
  gemini_pro_extend, outpaint_images, outpaint_16_9, watermark_clean,
  image_pair_prompts, generate_all_videos).
- 7 tests moved → `legacy/tests/`.
- `requirements-review.txt` → `legacy/requirements-review.txt`.
- `legacy/README.md` rewritten with full migration map.

### Docs
- `docs/roadmap/phase_6_subplan_2_execution.md` — this file.
- `docs/roadmap/phases.md` — Phase 6 scope note updated.

## What remains for Phase 6

Three more sub-plans as separate work:

- **Sub-Plan 3**: README rewrite for commercial positioning.
- **Sub-Plan 4**: `/app-design` + `/frontend-design` final passes.
- **Sub-Plan 5**: Deploy — Vercel frontend + self-hosted backend.

Phase 6 task stays `in-progress` until all three land.
