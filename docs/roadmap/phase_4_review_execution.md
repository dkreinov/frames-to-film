# Phase 4 — Review Sub-Plan Execution Log

**Sub-plan:** 5 of 5 (Review+Export) — last wizard screen.
**Status:** done
**Plan:** `plans/plan-20260424-0001.md` (self-deleted on close-out)
**Dates:** 2026-04-23 → 2026-04-24

## Outcome

Review & Export screen fully wired. User lands on Review after
Generate, sees each produced clip as a `SegmentReviewRow` with two
thumbs + a video lightbox + 3 verdict buttons (winner/redo/bad).
Clicking a verdict fires `POST /segments/{seg_id}/review`; the UI
updates only on mutation success (no optimistic rollback).
"Stitch & Export" button POSTs `/stitch`, polls the job with the
frozen pattern, and on done swaps to a plain
`<a href="/download" download>` link styled like a primary button.
Phase 4's core wizard (5/5 screens) is complete.

- 101/1 backend regression (up from 98; +3 `GET /segments` tests).
- 58/58 vitest (up from 44; +4 SegmentReviewRow + 7 ReviewScreen
  unit + 3 ReviewScreen integration).
- 10/10 Playwright (added review + review.golden).
- 7 golden PNGs tracked (Upload × 2, Prepare × 2, Storyboard × 1,
  Generate × 1, Review × 1).

## Frozen contracts introduced

- `GET /projects/{id}/segments` returning
  `{segments: [{seg_id, verdict, notes, updated_at}]}`, sorted by
  `seg_id`. Empty list when no reviews exist (200, not 404).
- `seg_id` canonical form: `seg_<pair_key>` (e.g. `seg_1_to_2`).
  Matches the produced video filename stem. Any future screen that
  touches segments MUST use this form.
- `api/client.ts`: `listSegments`, `reviewSegment`, `startStitch`,
  `downloadUrl`. Types `Verdict`, `Segment`.
- `SegmentReviewRow` component — reuse for any segment-verdict UI.
  3-button toggle group with `aria-pressed` + aria-label
  `Mark {pairKey} as {verdict}`.
- **Verdict POST-then-update pattern** (no optimistic update). Local
  state flips only inside `mutation.onSuccess`. Rejections leave
  the UI unchanged. Test `leaves aria-pressed unchanged if
  reviewSegment rejects` pins this.
- **setState-during-render seed-once pattern.** Canonical form
  documented in `docs/design.md`. MUST be accompanied by a
  `qc.refetchQueries` regression test that proves the guard holds
  under a real React Query refetch. Settings sub-plan and any
  future reconciliation screen should follow this contract rather
  than reinventing.
- **Download-via-`<a href download>`.** For any one-shot download
  flow, use a plain anchor styled with `buttonVariants`, not a
  `<Button>` + blob fetch. Browser handles progress, filename, and
  accessibility. Our `GET /download` already sends the right
  `Content-Disposition`.

## Decisions taken autonomously

- Q1 → A: verdict-only (no per-pair re-render). `redo` is advisory.
- Q2 → A: `GET /segments` so the UI survives a refresh.
- Q3 → B: explicit "Stitch & Export" button (not auto-stitch).
- Q4 → A: plain `<a download>` link (not blob fetch).
- Stitch: 1 attempt per budget. 5/5 sub-plans now timed out —
  pattern fully confirmed; plan Settings for hand-design up-front.
- Reused existing `VideoLightbox` + Radix `Dialog` primitive.
- `stitchStatus` follows the Generate sub-plan's user-triggered
  4-state enum (`idle|running|done|error`), matching the frozen
  contract for user-triggered screens.

## Advisor findings (2026-04-24 close-out)

### Resolved inline

1. **First regression test for seed-once was a placebo** — it
   called the mock fn directly instead of driving React Query.
   Replaced with a real `qc.refetchQueries` test that actually
   pipes fresh data through the component pipeline. Now fails if
   the `!verdictsSeeded` guard is removed.
2. **phases.md wording confusion risk** — "1 remaining (Settings)"
   could read as a 6th wizard screen. Clarified: "Wizard core
   complete (5/5 screens); non-wizard Settings remaining."

### Kept deliberately (documented)

1. **Verdict buttons `size="sm"` (32px)** are below the 44×44 touch
   baseline. Desktop-first; Phase 6 polish.
2. **Optimistic verdict updates NOT used** — the UI flips only on
   POST success. Prevents phantom verdicts on 5xx.

### Flagged for Settings sub-plan (6/6)

1. **Seed-once pattern is now frozen** — if Settings has any
   "server → local editable state" flow (e.g., API keys), use the
   canonical form + the `qc.refetchQueries` test harness.
2. **No need to retry Stitch MCP.** 5/5 timeout rate;
   just hand-design up-front.
3. **`seg_id = "seg_<pair_key>"` is frozen.** Don't reinvent.

## Follow-ups that don't belong to any sub-plan

- Phase 6 bump verdict buttons to `size="default"` (44×44) or add
  responsive mobile rule.
- Phase 6 wizard "Back" link across all screens.
- Phase 6 segment notes input (backend already accepts `notes`).
- Phase 6 per-pair "Regenerate" trigger — requires a new backend
  endpoint `POST /projects/{id}/generate/{pair_key}`.
- Phase 6 partial-stitch (winners-only) variant if users request it.
- Phase 6 retrofit Storyboard's `page.waitForTimeout(500)` to the
  `waitForRequest('**/order', {method: 'PUT'})` pattern used in
  Generate + Review E2E (carried over from Generate sub-plan).
