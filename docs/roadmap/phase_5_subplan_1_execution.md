# Phase 5 — Sub-Plan 1 Execution Log (web-mode scaffolding)

**Sub-plan:** 1 of 2 (mode plumbing + adapter skeleton).
**Status:** done
**Plan:** `plans/plan-20260424-0933.md` (self-deleted on close-out)
**Date:** 2026-04-24

## Outcome

`web` is now a legal third value of `Mode` across backend and frontend.
`VeoWebAdapter` stub exists at `backend/adapters/veo_web.py` with method
signatures Phase 5 Sub-Plan 2 will implement against a real Playwright
session; every real-browser method currently raises
`WebModeNotImplemented`. The generate-videos runner catches that
sentinel and converts it into a clean job error — the UI sees
`status='error'` with a user-facing "flip to mock or api" message, not
a 500. Settings shows a three-column table (mock / api / web) with the
Generate videos row exposing a disabled web radio + inline note; other
rows render a blank web cell.

No real browser automation yet. Sub-Plan 2 is where the actual Veo
pipeline lands, and it requires the user's authenticated Chrome profile
— deferred until the user is present.

- 10/10 backend generate tests (5 pre-existing + 3 new web-mode + 2
  reused router acceptance tests).
- 82/82 vitest (up from 72; +4 useSettings web-mode tests + 6 new
  SettingsScreen web-column tests).
- 3/3 settings Playwright specs (positive header attach + negative
  absence + golden capture). Golden regenerated to match the new
  three-column layout.

## Frozen contracts introduced

- **`Mode` type**: `'mock' | 'api' | 'web'`. `web` applies only to
  `generateVideos` today; other stages render a blank web cell.
  api/client.ts stage-start signatures widened correspondingly; per-
  stage UI gates + backend `Literal` validation keep invalid
  combinations unreachable at runtime.
- **`VeoWebAdapter`** interface at `backend/adapters/veo_web.py`.
  Methods: `authenticate`, `upload_frame`, `request_generation`,
  `download_clip`, `cleanup`. Sub-Plan 2 MUST NOT rename. Class is a
  context manager so `cleanup()` runs on failure paths.
- **`WebModeNotImplemented` sentinel** — `NotImplementedError`
  subclass that the generate runner catches specifically. Any future
  "stub-first, implement-later" adapter MUST reuse this pattern.
- **`STAGE_ROWS` shape for Settings** — each row now declares
  `apiEnabled: boolean` + `supportsWeb: boolean`. Pattern extensible
  to new vendors by adding a boolean + column header.
- **`run_generate` mode dispatch** — still raises `ValueError` on
  unknown modes, but `web` now has a branch. Sub-Plan 2 replaces the
  adapter raises with real work; the runner branch stays untouched.

## Decisions made during execution

- **Split Phase 5 into two sub-plans.** Full Phase 5 adapter requires
  user presence. Sub-Plan 1 lands everything Sub-Plan 2 will need as
  infrastructure, so Sub-Plan 2 is a drop-in replacement of the
  `raise WebModeNotImplemented(...)` lines with real Playwright.
  Alternative (defer all Phase 5 work until the user is around) would
  have stranded the user with a hard 0→100 jump. The split turns it
  into 0→80 (done) + 80→100 (user-supervised).
- **Sentinel subclass over magic flag.** Catching bare
  `NotImplementedError` in the runner would hide real bugs in future
  Sub-Plan 2 code (e.g., a child method forgot to implement a leaf
  step). `WebModeNotImplemented` is the only class caught; everything
  else propagates as a 500.
- **Widen `api/client.ts` stage signatures to `'mock' | 'api' | 'web'`**
  rather than narrow-per-stage. The UI gate (Settings only lets
  `generateVideos` flip to web) + backend `Literal` validation (prepare
  / extend / prompts / stitch all keep `Literal['mock','api']`)
  together prevent a `web` value from reaching a runner that doesn't
  handle it. A narrower per-stage TS type would add complexity for
  marginal safety.
- **Per-row `supportsWeb: boolean` over generalised `supportedModes: Mode[]`.**
  Currently only one stage supports web and only web is the new mode.
  Speculative generality would obscure the table code today. If a
  third vendor lands with a third enabled mode, revisit.
- **Disabled web radio with inline note over hiding the column.**
  Consistent with the Phase 4 Sub-Plan 6 decision for api-mode rollout
  — users see the roadmap instead of being surprised by a feature
  appearing later.

## Adjustments from the original plan

- None significant. One micro-adjustment in Step 5: widening the
  `api/client.ts` signatures was needed because TypeScript rejected
  the Mode → narrow-literal coercion at the four stage-screen call
  sites (PrepareScreen, StoryboardScreen, GenerateScreen,
  ReviewScreen). Fix was a 5-line sed, not a new sub-step.

## Files touched

### Backend
- `backend/routers/generate.py` — `GenerateRequest.mode` widened to
  `Literal['mock','api','web']`.
- `backend/adapters/__init__.py` — new empty package marker.
- `backend/adapters/veo_web.py` — new adapter + sentinel exception.
- `backend/services/generate.py` — new `mode == 'web'` branch dispatching
  to adapter with `WebModeNotImplemented`-catch.
- `tests/backend/test_generate_web.py` — new, 3 tests.

### Frontend
- `frontend/src/routes/useSettings.ts` — `Mode` type + tests.
- `frontend/src/routes/useSettings.test.ts` — +4 web-mode tests.
- `frontend/src/api/client.ts` — 5 stage-start signatures widened.
- `frontend/src/routes/SettingsScreen.tsx` — STAGE_ROWS reshape,
  three-column render, web-radio gating.
- `frontend/src/routes/SettingsScreen.test.tsx` — +6 web-column tests.
- `docs/design/golden/phase_4_settings.png` — regenerated (3-col).

### Docs
- `docs/design.md` — 5 new frozen-contract entries + 2 decisions rows.
- `docs/roadmap/phases.md` — Phase 5 → `in-progress`.
- `docs/roadmap/phase_5_subplan_1_execution.md` — this file.

## What Sub-Plan 2 needs (handoff)

Sub-Plan 2 requires the user's authenticated `.gemini_chrome_profile/`
pattern (documented in the `reference_gemini_web_automation` memory
note). Concretely, Sub-Plan 2 MUST:

1. Replace each `raise WebModeNotImplemented(...)` in
   `backend/adapters/veo_web.py` with a real Playwright step.
2. NOT rename any method on `VeoWebAdapter` — the runner branch in
   `backend/services/generate.py` binds to those names.
3. Extend `run_generate`'s web branch to actually iterate frames +
   upload + generate + download — the loop skeleton is sketched in
   the branch as a comment.
4. Add an integration test with a mocked `VeoWebAdapter` that returns
   bytes — NOT a real browser test; real-browser verification is a
   Claude-in-Chrome smoke test, not a CI test.
5. Flip `supportsWeb`'s disabled-radio behavior: remove the `disabled`
   when `m === 'web' && supportsWeb` so the user can actually flip
   the radio.
6. Flip the WEB_NOTE from "arrives in" to either a blank string or
   "requires authenticated Chrome profile" — a runtime note, not a
   roadmap note.
