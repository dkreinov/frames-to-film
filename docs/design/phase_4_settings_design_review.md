# Phase 4 Settings — Design Review

**Reviewer:** advisor pre-close-out + manual heuristic pass.
**Date:** 2026-04-24
**Baseline:** 8-point grid, ≥4.5:1 contrast, focus states,
empty/loading/error states, keyboard nav, touch targets ≥44×44.

Settings is a non-wizard route. No stage job runs here, no
polling, no stitch. Two concerns only: the user's Gemini key
and per-stage mock/api toggles.

## Critical findings — addressed inline

1. **AppBar lied about wizard state.** First pass rendered
   `<AppBar currentStep="upload" />` because `currentStep` was
   typed required — cheapest path to a compile. But the stepper
   then highlights "Upload" when the user is on `/settings`,
   which is a real visual bug a user would see immediately.
   Fix: made `currentStep` optional in both `AppBar` and
   `WizardStepper` (`findIndex` returning -1 for unknown is
   already graceful — no step renders active). Settings now
   passes no prop. Recorded as a Frozen contract so no future
   non-wizard route reinvents the same lie.

2. **Positive Playwright spec was authenticity-thin.** The
   original `settings.spec.ts` only asserted that
   `x-gemini-key === 'test-key-abc'` reached the backend after
   saving. That would pass even if `apiFetch` hardcoded the
   header. Added a negative test that clears localStorage and
   asserts no request in the first 1.5 s of PrepareScreen
   mounting carries the header. Together the two tests pin the
   real invariant: header sourced from localStorage, nothing
   else.

3. **`generate_prompts_api` signature + shadowing.** Backend
   `prompts.py` had `for key in pairs: ...` which would have
   shadowed a newly-added `key: str` parameter. Renamed loop
   var to `pair_key` before wiring the key through. Without
   this fix, the runner would have forwarded the pair string
   to `_get_genai_client` — a silent bug only caught by the
   unit test that passes `key="test-key"`.

4. **`resolve_gemini_key` as utility, not `Depends`.** First
   instinct was `Depends(resolve_gemini_key)` on every prompts
   route. That would make mock-mode requests 400 without a
   key — the exact thing the "runs offline for free"
   principle rules out. Moved to a plain function that
   handlers call only inside the `mode == "api"` branch.

5. **Key storage: client-only, never on the backend.** The
   tool ships for other people to run locally. Storing a key
   in the backend's `.env` is fine for the original dev but
   hostile to anyone else — they'd have to edit a file to
   paste a key. localStorage + header is the only shape that
   scales. Backend env var stays as a dev convenience
   fallback but is explicitly second-precedence.

## Checklist pass

- **Contrast:** shadcn zinc tokens throughout. Input border
  `--color-input`, placeholder uses `text-muted-foreground`
  which measures ≥4.5:1 against `--color-background`.
- **Focus rings:** Input uses
  `focus-visible:ring-[3px] focus-visible:ring-ring/50`.
  Show/Save/Clear buttons inherit shadcn ring. Radio inputs
  use native browser focus (acceptable — table rows give
  spatial context).
- **Empty / loading / error:** Not applicable — no async
  state renders on Settings. Save and Clear are synchronous
  localStorage writes.
- **Keyboard:** label `htmlFor="gemini-key"` connects to the
  input; all buttons are native `<button>`; radios are native
  `<input type="radio">` grouped by `name`. Tab order is
  key → show → save → clear → first radio → remaining radios.
- **Touch targets:** Buttons `size="sm"` (32px) — below 44×44.
  Consistent with rest of Phase 4; Phase 6 polish pass will
  address universally, not per-screen.
- **8-point grid:** `space-y-3`, `mb-10`, `mb-3`, `mb-4`,
  `px-3 py-2`, `w-96`, `pb-2`, `py-2`, `gap-2`.
- **Copy:** placeholder `sk-...` matches the shape of a
  Gemini API key. Help text explicitly calls out browser-only
  storage and the header name — this is a security claim the
  user deserves to see.

## Frozen-contract additions (approved by advisor)

- **`useSettings` hook + localStorage schema** —
  `olga.keys = {gemini: string}` +
  `olga.modes = {prepare, extend, generatePrompts,
  generateVideos, stitch: 'mock' | 'api'}`. Cross-tab sync
  via `storage` event listener.
- **`X-Gemini-Key` header attach pattern** — all client
  functions go through `apiFetch`; the header is read from
  localStorage on each call, never cached, so Save takes
  effect on the next request without a re-render.
- **`resolve_gemini_key` backend utility** — header → env →
  400. Called only on `mode == "api"` branches. Template
  for future per-vendor keys in Phase 5.
- **Mode propagation via `useSettings`** — every wizard
  screen that starts a job passes `modes.<stageKey>` to the
  mutationFn explicitly. Placebo tests that call the mock
  directly are banned — tests must drive the real mount path
  with `localStorage` seeded before render.
- **Non-wizard `AppBar`** — `currentStep` is optional;
  non-wizard routes pass nothing.

## Known gaps / explicitly deferred

- **Kling key input** — stub in Phase 5 when the Kling/Veo
  web adapter lands. Adding the field now without a working
  backend path would be a decorative input the user could
  type into with no effect.
- **Other-stage api radios** — render disabled with the
  "api mode arrives in Phase 5" note so the user sees the
  roadmap. Alternative (hide until ready) was rejected: the
  disabled-with-note form is honest and stops people from
  filing "toggle does nothing" bugs.
- **Phase 6 touch-target polish** — uniform 44×44 sweep
  across all interactive elements.

## Golden screenshot

`docs/design/golden/phase_4_settings.png` — captures the
filled-key (show mode on) + Generate prompts flipped to api
state. Regenerated after the AppBar fix so the stepper
correctly shows no active step on `/settings`.
