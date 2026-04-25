# Wet Test Findings — Phase 7 Input

**Date:** 2026-04-25  
**Test:** Full pipeline, 6 cat-astronaut fixtures, generate-prompts=api (Gemini), generate-videos=api (fal.ai Kling O3)  
**Output:** `full_movie.mp4` — 20 MB, 25.2 s (5 × 5-second clips concatenated)

---

## Findings

| # | Finding | Where | Severity | Suggested Fix | Phase 7 sub-plan? |
|---|---------|--------|----------|--------------|-------------------|
| 1 | **FAL_KEY not inherited by backend process** — backend started via `source .env` in bash, but env vars aren't propagated because Windows Git Bash background processes lose the env context on process restart. The `X-Fal-Key` header from the browser (via localStorage) is the real path; the `.env` fallback is unreliable on Windows. | `backend/deps.py:resolve_fal_key`, startup | High | Document that on Windows the keys must be pasted in Settings UI, or write a startup script that passes env vars explicitly to uvicorn via `--env-file`. | Yes — Phase 7 startup UX |
| 2 | **Settings UI keys not persisted on fresh browser session** — The settings page showed placeholder values (`sk-…`, `fal-…`) from browser autofill, but `olga.keys` was null in localStorage. The user had to manually save keys in Settings before any api-mode call would work; there was no clear indicator that keys were missing. | `frontend/src/routes/SettingsScreen.tsx`, `useSettings.ts` | High | Add a "keys missing" warning banner on the Generate page when mode=api but no key is stored. Auto-redirect to Settings if keys are absent. | Yes — Phase 7 onboarding |
| 3 | **fal.ai status URL format bug** — `kling_fal._submit()` constructed the polling URL by appending to the full model variant path (`fal-ai/kling-video/o3/standard/image-to-video/requests/{id}/status`), but fal.ai's queue API returns 405 on that path. The canonical status URL omits the variant suffix (`fal-ai/kling-video/requests/{id}/status`). **Fixed in-test** by hardcoding `_STATUS_BASE`. | `backend/services/kling_fal.py:_poll_until_done` | High (blocker) | Use `_STATUS_BASE = "https://queue.fal.run/fal-ai/kling-video/requests"` — already applied. Add integration test asserting submit→poll round-trip succeeds. | No — fixed |
| 4 | **fal.ai balance exhausted silently** — account had $0 despite auto-topup being "set up". First generate attempt returned 403 with `{"detail":"User is locked. Reason: Exhausted balance."}`. The frontend displayed a generic "400 Bad Request" error with no mention of billing. | `frontend/src/routes/GenerateScreen.tsx` error display | Medium | Parse the fal.ai 403 detail string and surface "Insufficient fal.ai balance — top up at fal.ai/dashboard/billing" instead of a raw HTTP error. | Yes — Phase 7 error UX |
| 5 | **Upload requires API call, not UI file picker** — The native file picker can't be triggered by browser automation (Playwright/Claude-in-Chrome). For E2E testing the project must be created via `POST /projects` + `POST /projects/{id}/uploads` directly. The UI upload zone has no programmatic alternative path. | `frontend/src/routes/UploadScreen.tsx` | Low | Expose a `data-testid="file-input"` attribute on the hidden `<input type="file">` so Playwright's `setInputFiles` can reach it without needing `page.evaluate`. | Yes — Phase 7 test infra |
| 6 | **Gemini prompt generation spinner hangs when first job fails** — When the initial `POST /prompts/generate` fails (e.g. key missing), the UI shows "Writing starter prompts…" indefinitely. `regenAttempted.current` prevents a second attempt, and the failure is only surfaced after a page reload. | `frontend/src/routes/GenerateScreen.tsx:promptsLoading` logic | Medium | Check `promptsGenMutation.isError` in the `promptsLoading` condition and show an error state (with Retry) instead of an infinite spinner. | Yes — Phase 7 error UX |
| 7 | **Stitch runs fast (mock mode confirmed)** — Stitching 5 × 5s clips into a 25.2s `full_movie.mp4` completed in under 3 seconds. ffconcat mock path works correctly; no blocking issues found. | `backend/services/stitch.py` | Info | — | No |
| 8 | **Per-pair fal.ai timing: ~60 s each** — Kling O3 standard processed each 5-second clip in ~59–62 s. 5 pairs × ~60 s = ~5 min total, within the 10-15 min budget. Cost: $0.084 × 5 = $0.42 (not $2.10 — the plan overestimated by 5×; actual clip count was 5, not 25). | `backend/services/kling_fal.py` | Info | Revise cost estimate in docs: 5 clips × $0.084 = ~$0.42 per 6-photo project. | No |

---

## Top 3 findings for Phase 7 backlog

1. **Missing-key warning on Generate page** (Finding 2 + 4) — most likely operator friction point. Show "no API key" and "billing issue" states explicitly.
2. **fal.ai status URL fix** (Finding 3) — already patched; needs automated integration test to prevent regression.
3. **Startup env var story on Windows** (Finding 1) — document Settings-UI-paste as the supported path; remove the `.env` fallback assumption from the operator guide.
