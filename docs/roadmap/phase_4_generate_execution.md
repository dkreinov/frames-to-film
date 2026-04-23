# Phase 4 — Generate Sub-Plan Execution Log

**Sub-plan:** 4 of 5 (Generate) — after Storyboard, before Review+Export.
**Status:** done
**Plan:** `plans/plan-20260423-2309.md` (self-deleted on close-out)
**Dates:** 2026-04-23

## Outcome

Generate screen fully wired. On mount it loads prompts via
`GET /projects/{id}/prompts`; if the file is missing OR its keys
drift from the current pair sequence (frames reordered in
Storyboard), exactly one `POST /prompts/generate` fires, polls, and
re-reads. Each pair renders as a `PromptRow` with an editable
textarea; edits fan in through `useDebouncedSave<Record<string,string>>`
to `PUT /prompts`. "Generate videos" kicks `POST /generate`, polls
via the frozen pattern, and on done fetches `GET /videos` to paint
a `VideoLightbox` poster inside each row. "Next: Review" routes
forward.

- 98/1 backend regression (up from 89; +4 videos tests + 5 PUT
  prompts tests + 4 pair-key harmonization tests).
- 44/44 vitest (up from 33; +3 PromptRow + 2 VideoLightbox + 5
  GenerateScreen unit + 3 GenerateScreen integration).
- 8/8 Playwright (added generate + generate.golden).
- 6 golden PNGs tracked (Upload × 2, Prepare × 2, Storyboard × 1,
  Generate × 1).

## Frozen contracts introduced

- `PUT /projects/{id}/order`-style atomic write for prompts:
  `PUT /projects/{id}/prompts` body `{prompts: {[pair_key]: string}}`
  (non-empty, all strings). Owner-scoped. Tempfile + `os.replace`.
- `GET /projects/{id}/videos` → `{videos: [{name, pair_key}]}`,
  ordered by `_ordered_frames(img_dir, project_dir)`. Returns
  `{videos: []}` when videos dir is missing.
- `_pair_keys_for_project` now honours `order.json` via the same
  `_ordered_frames`-style filter, so prompts.json is keyed to the
  pairs generate.py will actually render.
- `api/client.ts`: `startPromptsGeneration`, `getPrompts` (404 →
  null, matching the order endpoint contract), `savePrompts`,
  `startGenerate`, `listVideos`, `videoUrl`. Types `PromptsMap`,
  `VideoItem`, `StylePreset`.
- `components/generate/PromptRow` — reusable pair-edit row (two
  thumbs + pair-key + textarea + optional poster slot).
- `components/generate/VideoLightbox` — Radix-Dialog-wrapped
  `<video controls autoplay>`; poster button `aria-label="Play {pair_key}"`.
- `components/ui/dialog.tsx` — first introduction of Radix Dialog
  as the repo's canonical dialog primitive. Review / Settings
  sub-plans MUST reuse this rather than forking.
- **`regenAttempted` single-shot ref pattern** — for any future
  screen that auto-reconciles server state on mount, use one ref
  guard + an explicit error branch for the second failure instead
  of looping.

## Decisions taken autonomously

- Q1 → A: editable prompts with debounced PUT via the frozen
  `useDebouncedSave` hook. User agreed that order-of-operations
  concern (users don't know what to edit until they see a clip) is
  acceptable for a first-pass render.
- Q2 → A: auto-run `POST /prompts/generate` on mount. Consistent
  with Prepare / Storyboard; breaking the pattern would surprise.
- Q3 → B: poster thumbnail + Radix Dialog lightbox. Thumbnail-only
  render keeps initial paint light; `<video>` mounts only when open.
- Q4 → B: dedicated `GET /projects/{id}/videos` endpoint rather than
  widening `outputs/{stage}` to `{stage:path}`. Reason: /videos can
  later carry durations/thumbnails/etc. as the API grows.
- Stitch: 1 attempt per Upload-lesson budget (4/4 timed out now —
  budget confirmed correct). Fell back to hand-design notes in
  `docs/design/phase_4_generate_notes.md`.
- `generateStatus` enum is 4-state (`idle|running|done|error`), NOT
  the 4-state `pending|running|done|error` of the frozen polling
  pattern. Deliberate: Generate is user-triggered, so the initial
  state is `idle`, not `pending`. Documented in the design review.

## Advisor findings (2026-04-23 close-out)

### Resolved inline

1. **"Saved" pill flashed on loading screen** — gated on
   `prompts !== null` so the pill only mounts once a local map
   exists.
2. **Count error in phases.md** — after Generate it's 2 remaining
   (Review+Export, Settings), not 1. Caught before commit.

### Deliberately kept (rationale in design review)

1. **`generateStatus` 4-state enum shape** differs from the frozen
   polling pattern. Auto-start flows keep `pending`; user-triggered
   flows should mirror Generate's `idle`.
2. **Radix Dialog primitive in `components/ui/dialog.tsx`** is new.
   Review/Settings must reuse; noted in `docs/design.md` Frozen
   contracts.

### Flagged for follow-up sub-plans

1. **`regenFailed` reads `regenAttempted.current` during render** —
   works because other state changes co-occur, but brittle. Phase 6
   should replace with a `useState` signal.
2. **`useDebouncedSave` 5xx silence** still applies (same as
   Storyboard). Polish toast/rollback across all callers at once.
3. **`prompts.json` orphan keys after reorder** — `resolve_prompt`
   ignores them; Phase 6 should trim on next PUT.
4. **Prompts auto-regen needs a "frames changed" variant of the
   loading copy** — today it says "Writing starter prompts…" even
   when the trigger is a reorder. Copy polish.
5. **500-ms style debounce waits not used here** — we used
   `waitForRequest('**/prompts', {method: 'PUT'})` in Playwright,
   the cleaner replacement for the fixed sleeps flagged in
   Storyboard. Recommended for Storyboard + future sub-plans too.

## Findings for sub-plan 5 (Review+Export)

1. **`useDebouncedSave` is frozen** — if Review does any
   debounced-save (e.g., final trim/export-settings), use this hook.
   `T | null` + `skipNextNonNull` + StrictMode-safe.
2. **`_ordered_frames` + pair_keys precedence is frozen** — Stitch
   in Phase 5 and Review must not re-glob or re-sort.
3. **`components/ui/dialog.tsx`** is the canonical lightbox/dialog
   primitive. Don't fork.
4. **Playwright debounced-PUT assertions** — use
   `waitForRequest('<path>', {method: 'PUT'})` with a timeout, not
   `page.waitForTimeout(500)`. Storyboard's `waitForTimeout` should
   be retrofitted in Phase 6.
5. **Stitch is 0-for-4.** Budget 1 attempt per remaining sub-plan;
   plan for hand-design up-front.

## Follow-ups that don't belong to any sub-plan

- Phase 6 toast/rollback for `useDebouncedSave` save failures
  (promoted from "this sub-plan only" now that Generate joins the
  list).
- Phase 6 `regenFailed` ref → useState cleanup.
- Phase 6 prompts.json orphan-key trim on reorder.
- Phase 6 copy polish: "Frames changed — writing fresh prompts…".
- Phase 6 retrofit Playwright `waitForTimeout` to `waitForRequest`.
