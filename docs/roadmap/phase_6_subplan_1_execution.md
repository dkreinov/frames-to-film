# Phase 6 — Sub-Plan 1 Execution Log (E2E + CI)

**Sub-plan:** 1 of N (E2E journey coverage + GitHub Actions CI).
**Status:** done
**Plan:** `plans/plan-20260424-1804.md` (self-deleted on close-out)
**Date:** 2026-04-24

## Outcome

GitHub Actions CI now runs three parallel jobs on every push/PR to
master: backend pytest (116 tests), frontend vitest (93 tests), and
Playwright E2E against a real backend in mock mode. `ffmpeg` is
portable between Windows dev and Linux CI. A `phase_6_journey.gif`
captured via Claude-in-Chrome documents the wizard visually. No
subscription required for CI — all in mock mode.

- 116/116 backend pytest green + 2 skipped (fal-real smoke).
- 93/93 frontend vitest.
- 14/14 Playwright specs (per-screen + golden suites + settings).
- `review.spec.ts` is the canonical full-journey test — threads all
  5 wizard screens + stitch + download link in one spec.

## Key audit finding (Step 1)

A proposed `journey.spec.ts` was dropped after the Step 1 audit
showed `review.spec.ts` already covers the full happy path end-to-end
(Upload → Prepare → Storyboard → Generate → Review → Stitch →
Download link). Writing a second spec would duplicate coverage
without adding signal. Plan adjusted inline to 6 executed steps.

## Frozen contracts introduced

- **`.github/workflows/test.yml`** — single workflow, three jobs
  (`backend-tests`, `frontend-unit`, `e2e`). Any future test surface
  joins this workflow, NOT a new one. Ubuntu-latest + Python 3.12 +
  Node 20 is the frozen runner profile.
- **`requirements-test.txt`** — minimum backend test deps for CI
  (pytest + python-dotenv + requests). Kept tiny; heavy Streamlit
  deps live in `requirements-review.txt` and never touch CI.
- **`_resolve_ffmpeg()` precedence** (`backend/services/generate.py`):
  `shutil.which("ffmpeg")` → `tools/ffmpeg.exe` fallback. Same pattern
  already in `concat_videos.py`. Any new binary dependency MUST use
  this precedence — never hardcode a platform-specific path.
- **`review.spec.ts` as the journey test** — the single Playwright
  spec responsible for full-wizard regression. Per-screen specs
  (`upload.spec.ts`, `prepare.spec.ts`, etc.) cover isolated screen
  behavior; `review.spec.ts` covers state handoff across all five.
  Any regression that spans >1 screen belongs here, not in a new
  spec file.

## Decisions made during execution

- **Dropped Step 4** (planned journey spec) after Step 1 audit
  showed `review.spec.ts` is the journey spec. Karpathy rule #2:
  don't add what's already there.
- **Tour GIF, not functional recording**. Claude-in-Chrome can't
  drive the native file picker, so the recorded GIF walks an
  already-seeded project instead of driving a real upload. Good
  enough for docs; Playwright's `setInputFiles` remains the
  automation path for CI.
- **Portability fix is tiny**. Swapping hardcoded `tools/ffmpeg.exe`
  for `shutil.which("ffmpeg")` preserves Windows while unblocking
  Linux CI. No deeper cross-platform refactor needed.
- **CI job count = 3** (not fewer). Splitting backend / frontend /
  e2e into separate jobs gives parallel log output + targeted
  failure isolation. One monolith job would hide which layer
  regressed first.
- **CI runs on master push and on PR against master**. No staging
  branch pattern yet; can add later without reshape.
- **Playwright report uploaded on failure only**. ~50 MB artifact;
  7-day retention. Green runs don't pollute storage.

## Adjustments from the original plan

- Step 4 (journey spec) dropped per audit (see above). Executed
  only 6 of the 7 planned steps.
- Step 6 (GIF) pivoted mid-execution — first attempted to drive
  the upload flow, discovered Claude-in-Chrome can't trigger the
  native file picker, switched to navigation-tour of a seeded
  project. Mid-recording a Settings HMR cache glitch made that
  screen render stale; hard-reload resolved it but only after the
  export was already queued. The shipped GIF is 5 frames covering
  the five wizard screens (Settings omitted); acceptable for
  docs. Can regenerate if Settings needs inclusion.

## Files touched

### Backend
- `backend/services/generate.py` — `_resolve_ffmpeg()` helper +
  `FFMPEG_BIN` now resolved dynamically.

### Root / config
- `requirements-test.txt` (new) — pytest + python-dotenv + requests.
- `.github/workflows/test.yml` (new) — 3-job CI workflow.

### Docs
- `MANUAL_TESTING.md` — appended Phase 6 Sub-Plan 1 section.
- `docs/design/golden/phase_6_journey.gif` (new) — 24 KB tour.
- `docs/roadmap/phases.md` — Phase 6 → in-progress.
- `docs/roadmap/phase_6_subplan_1_execution.md` — this file.

## Remaining Phase 6 work

Tracked as separate Phase 6 sub-plans, not blockers for what
just shipped:

- **Sub-Plan 2**: Legacy Streamlit move → `legacy/`. Delete
  `review_app.py`, move tests, drop `generate_all_videos.py` from
  active imports.
- **Sub-Plan 3**: README rewrite for commercial positioning.
- **Sub-Plan 4**: `/app-design` + `/frontend-design` final passes.
- **Sub-Plan 5**: Deploy target — Vercel for UI, self-host backend.

## Phase 6 status after this sub-plan

CI + E2E coverage is now the gate. Any regression across wizard
screens, typechecks, unit tests, or the 14 Playwright specs fails
the workflow. Shipping from here is a progressively smaller set of
polish tasks, each its own sub-plan.
