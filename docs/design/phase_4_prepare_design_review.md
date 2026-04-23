# Phase 4 Prepare — Design Review

**Reviewer:** manual heuristic review (the `/app-design` skill was not in
this session's skill list).
**Date:** 2026-04-23
**Baseline:** 8-point grid, ≥4.5:1 contrast, focus states,
empty/loading/error states, keyboard nav, touch targets ≥44×44.

## Critical findings — applied inline

1. **Start-mutation error was lost.** Advisor found this: if
   `POST /prepare` 5xx'd, the user was stuck on the spinner with no
   retry. Fixed by treating `startMutation.isError` as `status='error'`,
   plus a regression integration test. Not strictly a visual/design
   issue, but the UX bug was design-critical (user stranded).

## Checklist pass

- **Contrast:** uses shadcn zinc tokens already proven at ≥4.5:1.
- **Focus rings:** inherited from shadcn Button; no custom interactive
  elements in the grid.
- **Empty / loading / error:** all three states handled
  (`OutputsGrid` empty text, `JobProgressCard` spinner with
  `role="status"`, AlertTriangle card with `role="alert"`).
- **Keyboard:** no custom keyboard controls introduced; Next button is
  the only interactive element and shadcn handles focus.
- **Touch targets:** Next button uses `size="lg"` (40px tall) — fine
  for desktop. Mobile responsive pass deferred to Phase 6.
- **8-point grid:** `p-8`, `mt-6`, `mb-4`, `gap-4` throughout.
- **SR live region:** `role="status" aria-live="polite"` on the
  spinner card; `role="alert"` on the error card.

## Non-critical (flag for follow-up sub-plans)

1. **No per-file progress.** For large projects, the running state is
   an opaque spinner. Phase 6 or a dedicated Prepare v2 sub-plan can
   add a `<progress>` + "Prepared 3 of 10" text when the backend emits
   partial progress.
2. **Thumbnail order derived from file name sort.** Good enough for
   mock mode; real Prepare should preserve upload order. Flag for
   Phase 6.
3. **No "back to Upload" link.** If the user wants to add more photos,
   they have to navigate back via browser history. Cheap fix — add a
   text link to the Footer's `left` slot. Deferred so it lands
   consistently across all 5 wizard screens.
