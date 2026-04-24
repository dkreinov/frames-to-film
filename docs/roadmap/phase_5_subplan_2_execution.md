# Phase 5 — Sub-Plan 2 Execution Log (fal.ai Kling O3)

**Sub-plan:** 2 of 2 (paid fal.ai Kling O3 integration).
**Status:** done
**Plan:** `plans/plan-20260424-1727.md` (self-deleted on close-out)
**Date:** 2026-04-24

## Outcome

Phase 5 pivoted from the originally-scoped free Playwright/Veo web
automation to paid fal.ai Kling O3 (latest Kling 3.0 first+last-frame
variant). User pastes a fal.ai API key in Settings, flips "Generate
videos" to api, clicks generate, and the backend issues a real
queue-based call to fal.ai's Kling O3 endpoint, polls until complete,
and downloads the mp4 per photo pair. 5-second clips, audio off,
$0.084/s = ~$0.42 per clip, ~$2.10 per typical 5-pair movie.

No Playwright browser automation, no Chrome profile, no CAPTCHAs.
Direct HTTP via `Authorization: Key <FAL_KEY>`.

- 24/24 backend tests (7 generate + 3 fal-resolver + 3 kling-fal unit
  + 3 generate-api-fal integration + 1 real smoke [skipped in CI] +
  pre-existing coverage).
- 93/93 vitest (+10 vs Sub-Plan 1 end: 4 useSettings fal tests,
  6 SettingsScreen fal+enable tests, 5 api-client fal-header tests,
  minus removed web-mode tests).
- 4/4 settings Playwright specs (positive both-keys, negative no-keys,
  independence fal-only, golden).
- Golden regenerated with two-key layout.

## Why the pivot

Sub-Plan 1 built `'web'` Mode scaffolding for a Playwright free path.
When we got to Sub-Plan 2, two facts made that plan unworkable:

1. **Veo (Google's free-via-Gemini-web) doesn't support first+last
   frame interpolation.** Takes a single reference image. The project
   NEEDS dual-keyframe interpolation between two photos — that's the
   whole pipeline.
2. **Grok Imagine API doesn't support end-frame either.** Confirmed
   via fal.ai docs: only `image_url`, no `end_image_url`.

Kling is the only vendor with native dual-keyframe. It's literally why
the repo has a `kling_test/` folder. Official Kling dev API has
awkward credit-pack minimums (user flagged the "$10 once per user"
tier oddity). fal.ai wraps Kling with pay-as-you-go pricing, simpler
auth (single static key, no JWT dance), and uniform inventory across
Kling/Luma/Veo/Runway for easy vendor swaps later.

So Sub-Plan 2 Steps 2-3 reverted the `'web'` scaffolding (adapter
stub + Mode enum + Settings column), and Steps 4-13 built the fal.ai
path in its place.

## Frozen contracts introduced

- **`Mode` re-narrowed** to `'mock' | 'api'`. Sub-Plan 1's `'web'`
  value is gone. api/client stage-start signatures narrowed
  correspondingly.
- **`resolve_fal_key(x_fal_key)`** in `backend/deps.py` — header →
  env `FAL_KEY` → `HTTPException(400)`. Called only on api-mode
  branches. Mirrors `resolve_gemini_key`.
- **`backend/services/kling_fal.py`** — `generate_pair(image_a,
  image_b, prompt, fal_key, duration=5) -> bytes`. Single adapter
  against fal.ai's queue REST API (`queue.fal.run`). Submit → poll
  → fetch → download. Method signature is frozen; any future vendor
  adapter (Luma, Runway) MUST use this shape.
- **`X-Fal-Key` header** — frontend `apiFetch` reads
  `olga.keys.fal` from localStorage and attaches on every request
  (mode-independent). Backend resolves only on api-mode generate.
- **Frontend `Keys.fal: string`** — second API-key field in
  Settings, styled identically to the Gemini input via a shared
  `KeyField` component.
- **5-second clip hardcode** — `backend/services/generate.py`
  `_API_DURATION_S = 5`. Promote to a per-project setting only if
  users actually ask for variable durations.
- **`KeyField` sub-component** in `SettingsScreen.tsx` — factored
  out during Step 9 to avoid duplicating the show/save/clear UI
  between Gemini and fal inputs. Future keys plug in as a third
  `<KeyField …/>` call.

## Decisions made during execution

- **Delete Sub-Plan 1 scaffolding outright.** Keeping `'web'` as a
  "future free path" would carry dead code indefinitely. Re-adding
  it later is 10 lines if needed. Karpathy rule #2.
- **Data URIs over image upload.** fal.ai accepts both HTTPS URLs
  and base64 data URIs. Data URIs keep the adapter self-contained
  (no presigned-URL dance). Cost: ~1.3x request size vs URL path,
  negligible for our ~200 KB frames.
- **Polling schedule 3→5→8→10→15s.** fal.ai Kling O3 typically
  completes in 1-3 min. Starts short to catch fast completions,
  ramps to 15s to avoid hammering the queue.
- **Auth on submit/status/result but not on CDN download.** The
  mp4 URL fal.ai returns is a pre-signed CDN URL; re-sending
  `Authorization: Key` on that breaks it. Tested explicitly.
- **Sentinel-only catch in runner** — same pattern as Sub-Plan 1's
  WebModeNotImplemented but now applied differently: the fal.ai
  path lets `requests.HTTPError` / `RuntimeError` bubble up
  normally. Only `resolve_fal_key` HTTPException is caught at
  the router (synchronous 400), not the runner.
- **KeyField aria-label** uses field id, not field label text.
  Using the label text in the Show/Hide button's aria-label
  caused `getByLabelText` to match two elements (input +
  button) in vitest. Using id (`Show gemini-key value`) keeps
  the labels unique and stable.
- **Golden captures both keys shown + both api radios flipped.**
  Snapshot of the "user-configured" Settings state — what the
  user sees when they've set up api mode for everything the UI
  currently allows.

## Adjustments from the original plan

- Step 6 and Step 7 ran back-to-back (one commit each) because the
  integration test in Step 6 required the router header to be
  wired. Plan called them separate; execution showed they're
  effectively atomic.
- Step 9 required an extra mid-step fix: refactoring SettingsScreen
  into a `KeyField` sub-component exposed a vitest selector
  collision (Show/Hide button aria-label matched field labels).
  Fixed inline by using the field id in the aria-label.
- Legacy `generate_all_videos.py` (475 lines, direct-Kling JWT) is
  now orphan code — no imports from `backend/`. Left untouched per
  the plan-skill rule "don't delete pre-existing dead code unless
  asked". Can be removed in Phase 6 cleanup.

## Files touched

### Backend
- `backend/deps.py` — `resolve_fal_key` added.
- `backend/services/kling_fal.py` — new adapter.
- `backend/services/generate.py` — api branch swapped from
  `generate_all_videos.run` to `kling_fal.generate_pair`; loads
  prompts.json per project.
- `backend/routers/generate.py` — `X-Fal-Key` header param;
  `resolve_fal_key` on api-mode POSTs.

### Backend tests
- `tests/backend/test_fal_key_resolver.py` — new, 3 tests.
- `tests/backend/test_kling_fal.py` — new, 3 tests (mocked HTTP).
- `tests/backend/test_generate_api_fal.py` — new, 3 integration tests.
- `tests/backend/test_kling_fal_real.py` — new, skipped without FAL_KEY.

### Backend cleanup (Sub-Plan 1 revert)
- Deleted `backend/adapters/veo_web.py` + `__init__.py`.
- Deleted `tests/backend/test_generate_web.py`.
- `backend/routers/generate.py` — `Literal['mock','api']` narrowed.
- `backend/services/generate.py` — web branch removed.

### Frontend
- `frontend/src/routes/useSettings.ts` — `Keys.fal` added; `Mode`
  narrowed.
- `frontend/src/routes/SettingsScreen.tsx` — `KeyField`
  sub-component; fal.ai input; `apiEnabled=true` for generateVideos;
  dropped web column + `supportsWeb` + `WEB_NOTE`.
- `frontend/src/api/client.ts` — `headersWithKey` also emits
  `X-Fal-Key`; stage-start signatures narrowed.

### Frontend tests
- `frontend/src/routes/useSettings.test.ts` — web block deleted,
  fal block added (4 tests).
- `frontend/src/routes/SettingsScreen.test.tsx` — web block deleted,
  fal block added (4 tests). Existing tests updated for 2-Save
  button layout.
- `frontend/src/api/client.test.ts` — 5 new tests for X-Fal-Key.
- `frontend/e2e/settings.spec.ts` — 3 tests (both-keys, no-keys,
  fal-only).
- `frontend/e2e/settings.golden.spec.ts` — updated for new layout.
- `docs/design/golden/phase_4_settings.png` — regenerated twice
  (once after 'web' removal, once after fal input added).

### Docs
- `docs/roadmap/phases.md` — Phase 5 → done; scope restated.
- `docs/design.md` — frozen contracts updated for the pivot;
  decisions log extended.
- `docs/roadmap/phase_5_subplan_2_execution.md` — this file.

## Phase 5 close-out

All six sub-plans across Phases 4 and 5 shipped. Generate-videos now
has a real paid end-to-end path (Kling O3 via fal.ai) alongside the
mock path. Next: **Phase 6** — full E2E test suite, polish, ship.
