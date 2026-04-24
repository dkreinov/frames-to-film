# Phase 4 — Settings Sub-Plan Execution Log

**Sub-plan:** 6 of 6 (Settings) — closes out Phase 4.
**Status:** done
**Plan:** `plans/plan-20260424-0852.md` (self-deleted on close-out)
**Dates:** 2026-04-24

## Outcome

Settings route shipped at `/settings`. User pastes a Gemini API
key, saves to localStorage, flips "Generate prompts" to `api`,
and the very next `POST /projects/{id}/prompts/generate` ships
the key in an `X-Gemini-Key` header. Backend prefers header over
`.env` and only validates on `mode == "api"` branches so mock
mode stays free. Other stage radios render disabled with an
"api mode arrives in Phase 5" note. Phase 4 core (5/5 screens)
+ Settings = Phase 4 done.

- Backend regression green after signature change (key parameter
  plumbed through `prompts.py`, router, and runner; two existing
  tests fixed for the new `_get_genai_client(key)` signature;
  six new tests cover resolver precedence + endpoint behavior).
- 72/72 vitest (up from prior wizard baseline; +2 `useSettings`
  mode-propagation tests seeded with real localStorage).
- 12/12 Playwright — added `settings.spec.ts` (positive header
  attach + negative absence) and `settings.golden.spec.ts`.
- 8 golden PNGs tracked (Upload × 2, Prepare × 2, Storyboard × 1,
  Generate × 1, Review × 1, Settings × 1).

## Frozen contracts introduced

- **`useSettings` hook** + localStorage schema (`olga.keys` =
  `{gemini: string}`, `olga.modes` = `{<stage>: 'mock' | 'api'}`).
  Cross-tab `storage` event listener so a save in one tab
  propagates without reload.
- **`X-Gemini-Key` header attach pattern** via
  `apiFetch(url, init)` in `api/client.ts`. Every client
  function routed through this wrapper; header read from
  localStorage on every call, never cached, so Save takes
  effect on the next request.
- **`resolve_gemini_key` backend utility** in `backend/deps.py`:
  header → env → `HTTPException(400, ...)`. Handlers call it
  only on `api`-mode branches. Template for future per-vendor
  key resolvers (Kling, OpenAI) in Phase 5.
- **Mode propagation via `useSettings`.** Every wizard screen
  that starts a stage job reads `modes.<stageKey>` and passes
  it to the mutationFn explicitly. Unit tests must drive the
  real mount path with `localStorage` seeded before render —
  placebo tests that call the client mock directly are banned.
- **Non-wizard `AppBar`.** `currentStep` is optional; non-wizard
  routes render `<AppBar />` with no prop so the stepper
  highlights nothing. Never pass a fake step id to satisfy the
  type — it lies to the user.

## Decisions made during execution

- **localStorage, not server-side user accounts.** This tool
  ships for other people to run locally. A key baked into the
  backend's `.env` is hostile to any other user. localStorage
  + header is the only shape that scales across users without
  adding auth infrastructure.
- **Per-stage mode toggle now, not vendor toggle later.** Each
  stage may land on a different vendor in Phase 5 (Kling web,
  Veo web, Minimax). A per-stage toggle lets each row flip
  on as its path lands without redesigning Settings.
- **Disabled radios with inline note, not hidden rows.** User
  sees the whole roadmap, understands why four of five rows
  can't flip yet, and doesn't file "my toggle does nothing"
  bugs during Phase 5 staging.
- **Only `generatePrompts` enabled today.** Backend Gemini
  path is the only one that actually works in api mode right
  now. Shipping other radios enabled would be a lie.

## Adjustments from the original plan

- Made `AppBar`'s `currentStep` optional rather than passing
  `"upload"` from Settings. Advisor-flagged mid-Step 7 before
  docs commit — would have been an immediately visible user-
  facing bug.
- Added negative Playwright spec asserting header absence when
  no key is saved. Advisor-flagged — positive spec alone would
  pass even if `apiFetch` hardcoded the header.
- Renamed shadowing loop variable `key` → `pair_key` in
  `prompts.py` when adding the new `key: str` parameter. Silent
  bug only caught because the updated test passes `key="test-key"`.

## Files touched

### Backend
- `backend/deps.py` — new `resolve_gemini_key` utility.
- `backend/services/prompts.py` — `_get_genai_client(key)`,
  `generate_prompts_api(project_dir, style, key)`, runner reads
  `payload["gemini_key"]`. Loop variable renamed to avoid
  shadowing.
- `backend/routers/prompts.py` — `x_gemini_key` header param;
  conditional resolution on `mode == "api"`.
- `tests/backend/test_prompts_generate.py` — two existing
  monkeypatch signatures updated; six new tests added for
  resolver precedence + endpoint behavior.

### Frontend
- `frontend/src/routes/useSettings.ts` — new hook.
- `frontend/src/api/client.ts` — `headersWithKey` +
  `apiFetch` wrapper; all 18 `fetch` call sites routed through
  `apiFetch`.
- `frontend/src/routes/SettingsScreen.tsx` — new route.
- `frontend/src/routes/router.tsx` — `/settings` lazy route.
- `frontend/src/routes/PrepareScreen.tsx`,
  `StoryboardScreen.tsx`, `GenerateScreen.tsx`,
  `ReviewScreen.tsx` — consume `modes` from `useSettings`.
- `frontend/src/components/layout/AppBar.tsx`,
  `WizardStepper.tsx` — `currentStep` prop optional.

### Tests
- `frontend/src/routes/PrepareScreen.test.tsx` and
  `GenerateScreen.test.tsx` — +1 mode-propagation test each.
- `frontend/e2e/settings.spec.ts` — 2 tests (positive header
  attach + negative absence).
- `frontend/e2e/settings.golden.spec.ts` — golden capture.

### Docs
- `docs/design.md` — frozen contracts + decisions log entries.
- `docs/design/phase_4_settings_design_review.md` — new.
- `docs/design/golden/phase_4_settings.png` — new.
- `docs/roadmap/phases.md` — Phase 4 → done.

## Phase 4 close-out

All six sub-plans shipped: Upload, Prepare, Storyboard, Generate,
Review+Export, Settings. Frozen contracts collected in
`docs/design.md` serve as the input to Phase 5 (web-mode video
generation) — the `resolve_<vendor>_key` + `X-<Vendor>-Key`
pattern is the template for any new secret Phase 5 introduces.
