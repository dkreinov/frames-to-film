# Manual Testing — Phase 4 Wizard QA Pass

**Date:** 2026-04-24
**Scope:** Phase 4 sub-plans 1–5 (Upload → Prepare → Storyboard → Generate → Review+Export).
**Driver:** `claude-in-chrome` (automated) + hand inspection of screenshots.
**Mode:** Backend mock mode throughout.
**Outcome:** Core wizard renders end-to-end. Several Phase 6 polish items identified; one real bug blocked on a tool-environment workaround.

## Environment

- Backend: `uvicorn backend.main:app --host 127.0.0.1 --port 8000` (mock-default stages).
- Frontend: `npm run dev` serving Vite on `127.0.0.1:5173` with React `<StrictMode>` enabled.
- Browser: Chromium via `claude-in-chrome` MCP tool.
- Fixture photos: `tests/fixtures/fake_project/frame_{1..4}_gemini.png` (4 input frames → 6 outpainted → 5 pair clips).

## Tooling caveat — READ BEFORE RE-RUNNING

Tabs opened via `claude-in-chrome` are treated as `document.visibilityState === 'hidden'`. TanStack Query's default `refetchIntervalInBackground: false` pauses polling in hidden tabs, so Prepare / Storyboard / Generate / Review all appear permanently stuck on their spinner. This is NOT an app bug under a real user's visible tab (Playwright E2E confirms the full flow works). It IS a real concern for real-user background-tab scenarios — see finding #4 below.

**Workaround for this QA pass:** after each `navigate`, inject:
```js
Object.defineProperty(document, 'hidden', { value: false, configurable: true })
Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
document.dispatchEvent(new Event('visibilitychange'))
```
A `setInterval` rerunning this every 500ms is safer because Chrome may re-assert `hidden=true` on tab state changes.

## Happy-path summary

| Screen | Rendered | Notes |
|---|---|---|
| Upload (empty) | ✓ | Clean dropzone, stepper shows "1 Upload" highlighted, Next disabled. "backend ok" pill bottom-right. |
| Prepare (running) | ✓ (with workaround) | Spinner card "Preparing photos…" with subcopy. Clean. |
| Prepare (done) | ✓ | "Prepared 6 photos", 6-tile grid. First tile bright; others dark due to letterbox padding on the 4:3 outpaint — expected, not a bug. |
| Storyboard | ✓ | 6 thumbnails, position badges 1–6, drag handles (top-right, 9-dot icon), "Order saved" pill. Auto-extend completed cleanly. |
| Generate (prompts ready) | ✓ | 5 pair rows visible, each with thumbnail-pair + pair_key + textarea seeded with the cinematic preset. "Saved" pill top-left. "Generate videos" action button bottom-right. |
| Review | ✓ | 5 segment rows with play buttons + Winner/Redo/Bad toggle groups. "Stitch & Export" visible but partly below fold at 1080p. |

## Edge-case findings

Edge-case matrix (plan Step 3) was reduced given the tool-environment workarounds consumed the budget. What I did probe:

1. **Direct URL navigation to `/projects/:id/prepare` for an existing project** — wizard does not short-circuit. It re-POSTs `/prepare`. Idempotent in mock mode; would double-bill in api mode. Related to finding #2.
2. **`/projects/:id/upload` URL for a project that already has uploads** — shows empty "No photos yet" + disabled Next. Doesn't hydrate from `GET /uploads`. Unclear whether the edit-mode route should show existing uploads or redirect forward.

Not probed (carry into Phase 6 manual/Playwright coverage):
- Refresh mid-Storyboard after drag (Playwright covers the drag path; refresh-persistence needs manual verification).
- Bad file-type upload rejection.
- Browser back-button between steps.

## Categorized follow-ups

### Blockers (must fix before ship)

*None in the app itself.* The `refetchIntervalInBackground` finding (#4 below) is the closest — it IS user-facing but the common case (foreground tab) works correctly.

### Phase 6 polish

1. **`refetchIntervalInBackground` on stage-job queries.** Today, when a tab goes to the background, TanStack Query stops polling `/jobs/{id}`. On return-to-foreground it resumes, but the user sees a stalled spinner in the meantime. Setting `refetchIntervalInBackground: true` on the 4 screens that poll a stage job (Prepare, Storyboard, Generate, Review) keeps the UI honest without measurable cost.
   - **Fix sketch:** each `useQuery({ refetchInterval: ... })` config also sets `refetchIntervalInBackground: true`. Pattern is one line per screen and belongs in `docs/design.md` Frozen contracts alongside the existing polling pattern.

2. **Upload edit-route shows empty state for existing projects.** `/projects/:id/upload` should either (a) hydrate the existing uploads list from `GET /uploads`, (b) redirect forward to `/prepare` if the project has any uploads, or (c) display a "this project already has uploads — continue to Prepare?" card. Today it silently shows the new-project UI.
   - **Fix sketch:** fetch `listUploads(projectId)` on mount; if non-empty, redirect or show continuation card.

3. **Double `POST /prepare` under React StrictMode.** The Prepare screen's mount effect fires twice in dev, producing two jobs. Idempotent in mock; wasteful in api mode. Same pattern applies to Storyboard's extend, Generate's prompts/generate, and Review's stitch auto-triggers elsewhere.
   - **Fix sketch:** use a module-level `AbortController` per `(projectId, kind)` pair, or gate mutation in the effect on `!mutation.isPending && !mutation.isSuccess`. Low urgency; prod build doesn't double-mount.

4. **Generate "Saved" pill copy is ambiguous.** Just "Saved" — user may not know what was saved. Suggest "Prompts saved" or a variant matching Storyboard's "Order saved".

5. **Stitch button below the fold at 1080p on Review.** With 5 segments × ~80px rows, the "Stitch & Export" card anchors near the bottom and can be partially clipped. Phase 6 polish: either sticky-pin the action card or shorten per-row padding.

### Cosmetic / nice-to-have

6. **Storyboard drag handle position** is top-right; most sortable UIs put handles top-left or center-left. Works fine but unusual. Low priority.
7. **Verdict buttons in Review are `size="sm"` (32px)** — flagged in the Review sub-plan's design review already. Below the 44×44 touch baseline.
8. **Prepare thumbnails appear "dark" for frames 2–6** because the outpaint pads the original 4:3 crops to 4:3 with darkness. Not a bug but surprising at first glance. A short caption ("letterboxed to 4:3") or a brief hover preview would clarify.
9. **No progress indicator on Prepare / Storyboard / Generate jobs.** Just a spinner. Phase 6 nice-to-have: show "Prepared N of M photos" when backend emits partial progress.

## What this pass does NOT cover

- Playwright-level interactive asserts (drag, verdict POST, stitch POST, download trigger) — already in e2e suite.
- Accessibility audit (screen reader, keyboard-only navigation, contrast ratios). `/frontend-design` or `/app-design` pass in Phase 6.
- Mobile / narrow viewport behaviour (desktop-only until Phase 6 polish).
- Settings screen (not built yet — sub-plan 6).

## Golden screenshot baselines

Existing Playwright-captured goldens in `docs/design/golden/` are the authoritative visual baselines for each screen:
- `phase_4_upload_empty.png`, `phase_4_upload_with_files.png`
- `phase_4_prepare_early.png`, `phase_4_prepare_done.png`
- `phase_4_storyboard_grid.png`
- `phase_4_generate_ready.png`
- `phase_4_review_ready.png`
- `phase_4_settings.png` (two-key layout: Gemini + fal.ai; generate-videos api enabled)
- `phase_6_journey.gif` (5-frame wizard tour via Claude-in-Chrome)

No fresh PNGs added from this pass — Playwright's existing set covers the visual states at higher fidelity than the MCP tool's screenshots.

---

# Phase 6 Sub-Plan 1 — Full E2E + CI

**Date:** 2026-04-24
**Scope:** Full happy-path E2E journey (already covered by `review.spec.ts`) + GitHub Actions CI running backend pytest + frontend vitest + Playwright E2E on every push. All in mock mode.

## E2E journey coverage

`frontend/e2e/review.spec.ts` drives the entire happy path in a single test:

1. `/projects/new/upload` → drop 3 fixture photos → click Next
2. `/projects/:id/prepare` → wait for "Prepared N photos" → Next
3. `/projects/:id/storyboard` → wait for drag handles → Next: Generate
4. `/projects/:id/generate` → wait for prompt textareas → click Generate Videos → wait for play buttons
5. `/projects/:id/review` → click Winner on first segment → Stitch & Export → assert "Download full movie" link

Cleanup: `DELETE /projects/:id` to keep tests idempotent.

No separate `journey.spec.ts` was added — would duplicate this coverage.

## Pre-CI portability fix

`backend/services/generate.py` previously hardcoded `tools/ffmpeg.exe`. Fixed to use `shutil.which('ffmpeg')` first, fall back to the Windows exe. Linux CI runners (`apt-get install -y ffmpeg`) now work; Windows dev unchanged.

## CI workflow

`.github/workflows/test.yml` runs on every push/PR to master:

- **backend-tests** (`ubuntu-latest`, Python 3.12): apt-install ffmpeg, pip install from `requirements.txt` + `requirements-test.txt` (new), pytest 116 tests.
- **frontend-unit** (`ubuntu-latest`, Node 20): npm ci, tsc -b, vitest run (93 tests).
- **e2e** (`ubuntu-latest`, Python 3.12 + Node 20): ffmpeg + npm ci + `npx playwright install --with-deps chromium` + `OLGA_PYTHON=python npx playwright test`. Uploads `playwright-report` artifact on failure.

Real fal.ai smoke test (`test_kling_fal_real.py`) auto-skips under CI (`pytest.mark.skipif(not FAL_KEY)`) — zero cost.

## Known Claude-in-Chrome limitation

Native file picker cannot be driven by the MCP tool for file uploads. The `phase_6_journey.gif` tour therefore walks an already-seeded project rather than starting from `/projects/new/upload` with a real file drop. Playwright's `setInputFiles` on the hidden `<input type=file>` is the canonical path for automated upload testing — see `review.spec.ts`.

## Deferred to later Phase 6 sub-plans

- Deploy to Vercel (frontend) + self-host backend
- Legacy Streamlit move → `legacy/`
- README rewrite for commercial positioning
- `/app-design` + `/frontend-design` final passes
- Settings → generate-videos full real-fal.ai E2E (requires user's paid key)

