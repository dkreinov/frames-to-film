# Phase 4 — Storyboard Sub-Plan Execution Log

**Sub-plan:** 3 of 5 (Storyboard) — after Prepare, before Generate.
**Status:** done
**Plan:** `plans/plan-20260423-1811.md` (self-deleted on close-out)
**Dates:** 2026-04-23

## Outcome

Storyboard screen fully wired. Auto-posts `/extend` on mount (Prepare
pattern), polls `/jobs` until done, then renders a sortable grid of
the 16:9 outpainted frames. Drag-to-reorder uses `@dnd-kit`; the new
order is debounced (300 ms) and PUT to a new
`/projects/{id}/order` endpoint that persists to
`<project>/order.json`. The Generate stage now consumes that file via
`_ordered_frames`, so user-arranged sequence flows end-to-end into
the mock + API video pipeline.

- 90/1 backend regression (up from 84; +6 order-router tests).
- 33/33 vitest (up from 22; +3 Storyboard unit + 3 Storyboard
  integration including a `<StrictMode>` regression + 2 hook tests +
  3 SortableThumbnail/Grid).
- 6/6 Playwright (upload, upload.golden, prepare, prepare.golden,
  storyboard, storyboard.golden).
- 5 golden PNGs tracked (Upload's 2, Prepare's 2, Storyboard's 1).

## Frozen contracts introduced

- `PUT /projects/{id}/order` body `{order: string[]}` (non-empty,
  all strings) → writes `<project>/order.json`. Owner-scoped.
- `GET /projects/{id}/order` → `{order: string[]}` or 404 before
  first PUT. Front-end maps 404 → `null`.
- `_ordered_frames(img_dir, project_dir)` in
  `backend/services/generate.py` is the canonical sort for any stage
  that consumes `kling_test/*.jpg`. Stitch + Review must reuse it.
- `generate_all_videos.PROJECT_ORDER` global swapped under
  `_RUN_LOCK` (mirrors `PROJECT_PROMPTS`). Don't add a second
  ordering channel — extend this one if Generate-API needs more.
- `frontend/src/api/client.ts` adds `startExtend`, `saveProjectOrder`,
  `getProjectOrder`. The 404 → `null` mapping lives in
  `getProjectOrder` (callers must handle null).
- `useDebouncedSave<T>(value: T | null, delayMs, save)` —
  null-gated, first-non-null skipped. Verified safe under
  `<StrictMode>`. Generate / Review must use this hook for any
  debounced PUT.
- DnD primitives: `@dnd-kit/core + /sortable + /utilities` with
  `PointerSensor({ activationConstraint: { distance: 4 } })` +
  `KeyboardSensor`, `rectSortingStrategy`, `arrayMove` on
  `onDragEnd`. Drag handle `aria-label` matches
  `/^Drag frame \d+ \(.+\)\./`.

## Decisions taken autonomously

- Backend persistence (Q1 = A): order lives in
  `<project>/order.json`, not localStorage. Survives device switches,
  enables Phase 5/6 server-side rendering. Endpoint is owner-scoped
  for parity with `/projects`.
- Auto-run extend on mount (Q2 = A): Prepare pattern. Storyboard has
  no Start button — same UX as Prepare's outpaint trigger.
- Stitch: 1 attempt (per Upload-lesson budget), timed out as
  predicted, fell back to hand-design.
- Pin a `<StrictMode>` regression test for `useDebouncedSave` rather
  than refactoring to the `lastSeen` ref pattern. The hook is
  empirically safe in React's actual double-effect cycle and the test
  proves it; refactor risk > benefit.

## Advisor findings (2026-04-23 close-out)

### Resolved inline

1. **Initial-load PUT echo on `/order`.** First integration pass fired
   a PUT immediately after server data hydrated `order` from `null` →
   `string[]`. Reshaped `useDebouncedSave` to accept `T | null` with
   `skipNextNonNull` ref. Pinned by integration test.

2. **`useDebouncedSave` under `<StrictMode>`.** Advisor flagged the
   `useRef(true)` skip flag could be consumed by StrictMode's
   intentional double-effect on initial mount. Verified safe with a
   regression test wrapping the rendered tree in `<StrictMode>` and
   asserting `putOrderCalls.length === 0` after 500 ms. Test passes
   because the seed effect runs on a *subsequent* render after server
   data resolves, not the initial double-mounted cycle.

### Flagged for follow-up sub-plans

1. **`useDebouncedSave` swallows save errors.** A 5xx on `PUT /order`
   silently clears `isPending`. Generate / Review will hit the same
   pattern; Phase 6 should add toast-on-error or local rollback.
2. **`order.json` orphan on reference drift.** If Generate ever
   renames frame files mid-flight, `_ordered_frames` silently falls
   back to numeric sort. Generate sub-plan must re-acknowledge the
   contract that `kling_test/*.jpg` filenames are stable post-extend.
3. **500 ms `waitForTimeout` in Playwright.** Debounce is 300 ms +
   network. If CI flakes, switch to `waitForRequest('**/order')`.
4. **dnd-kit bundle weight (~30 KB gz).** Lazy-load the Storyboard
   route in Phase 6 if Review doesn't end up needing the same
   primitives.

## Findings for sub-plans 4-5

1. **`useDebouncedSave` is the canonical debounce-then-PUT hook.**
   Generate (prompt edits → `prompts.json`) and Review (frame
   reorder → `order.json` again, or stitch settings) MUST consume it.
   Don't roll a new debounce ref.
2. **`_ordered_frames` is the canonical frame sort.** Any backend
   service that walks `kling_test/*.jpg` must call it (passing
   `project_dir`) so user ordering is honoured. Stitch sub-plan in
   particular: don't re-glob.
3. **Per-item `<button>` drag handle wins over wrapping the whole
   thumbnail as draggable.** Cleaner focus ring, cleaner
   `aria-label`, and Playwright can target by role+name. Reuse the
   `SortableThumbnail` component if Review needs another sortable.
4. **Playwright drag = mouse API + 4 px initial nudge.** Required to
   activate dnd-kit's PointerSensor. Keyboard drag is unreliable
   in headless Playwright; rely on a11y unit tests instead.
5. **One Stitch attempt per screen still holds.** Two of three
   sub-plans have hit the same timeout pattern; budget for it.

## Follow-ups that don't belong to any sub-plan

- Phase 6 toast/rollback for `useDebouncedSave` save failures.
- Phase 6 lazy-load Storyboard route if dnd-kit isn't reused.
- Phase 6 swap Playwright's debounce sleep for `waitForRequest`.
