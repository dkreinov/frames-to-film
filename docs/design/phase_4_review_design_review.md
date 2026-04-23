# Phase 4 Review — Design Review

**Reviewer:** advisor pre-close-out + manual heuristic pass.
**Date:** 2026-04-24
**Baseline:** 8-point grid, ≥4.5:1 contrast, focus states,
empty/loading/error states, keyboard nav, touch targets ≥44×44.

## Critical findings — addressed inline

1. **Seed-once `setState`-during-render pattern had no real test.**
   First pass of the regression test called the mock directly
   instead of forcing a React Query refetch, so the assertion
   would pass even if the guard were removed. Fixed to use
   `qc.refetchQueries` + `waitFor(toHaveBeenCalledTimes(2))` which
   pipes the fresh server data through the actual query pipeline.
   Test now pins the real invariant.

2. **Verdict POST-then-update vs optimistic.** First instinct was
   optimistic update with rollback on failure. Switched to
   update-only-on-success: the UI never shows a verdict the server
   hasn't recorded. Covered by the
   "leaves aria-pressed unchanged if reviewSegment rejects" unit
   test.

3. **Download link semantics.** Used a plain `<a href download>`
   styled with `buttonVariants({variant: 'default', size: 'lg'})`
   rather than wrapping `<Button>` + manual blob fetch. Correct
   semantics (browser treats it as a link, screen readers announce
   "link"), zero extra code, `GET /download` already sets
   `Content-Disposition: attachment`.

## Checklist pass

- **Contrast:** shadcn zinc tokens. Verdict buttons default to
  outline; selected flips to filled default variant for ≥4.5:1.
- **Focus rings:** all verdict buttons, VideoLightbox trigger,
  Stitch button, Download anchor have visible rings.
- **Empty / loading / error:** loading uses JobProgressCard
  ("Loading your clips…"); stitch running + error + done all
  reuse the same card. No "no videos" state because arriving
  here via Next: Review requires a completed Generate job.
- **Keyboard:** native `<button>` for verdicts, native `<a>` for
  download. Dialog focus-trap handled by Radix (reused from
  Generate).
- **Touch targets:** verdict buttons `size="sm"` (32px) — below
  44×44. Flagged for Phase 6 (see below).
- **8-point grid:** `space-y-3`, `p-4`, `space-y-6`, `gap-2`,
  `max-w-md`, `pt-4` throughout.
- **SR live region:** Stitch card is `role="status"` while running,
  `role="alert"` on error (inherited from `JobProgressCard`).

## Frozen-contract additions (approved by advisor)

- **`setState`-during-render seed-once pattern** is sound for
  reconciling "seed once from a query, never again" workflows.
  Canonical form:
  ```tsx
  const [seeded, setSeeded] = useState(false)
  if (!seeded && query.data) {
    setLocal(derive(query.data))
    setSeeded(true)
  }
  ```
  Required: a regression test that uses
  `QueryClient.refetchQueries()` to pipe fresh data through the
  component, proving the second pass does NOT overwrite local
  state. Without that test, a future refactor to `useEffect` can
  silently regress.

## Non-critical (flagged for follow-up sub-plans / Phase 6)

1. **Verdict buttons `size="sm"` are 32px** — below the 44×44
   touch target baseline. Desktop-first release; Phase 6 polish
   should bump to `size="default"` or add a mobile-responsive
   rule.
2. **No "back to Generate" link in the footer.** Same pattern
   carried from Upload/Prepare — the whole-wizard Back link lands
   in Phase 6.
3. **No notes input on rows.** Backend accepts them but the UI
   omits; keep scope tight. Phase 6 or post-MVP feature.
4. **No per-pair "Redo" trigger** (Q1=A chose verdict-only).
   Marking a segment as `redo` is purely advisory today; a future
   sub-plan can add "regenerate marked-redo pairs" once a per-pair
   generate endpoint exists.
5. **Stitch fires with all segments** regardless of `bad`
   verdicts. Intentional — partial-stitch (winners-only) is bigger
   scope.
6. **No progress indicator on download.** `<a download>` hands off
   to the browser's built-in UI. For files larger than ~100 MB,
   Phase 6 could add a progress overlay.
