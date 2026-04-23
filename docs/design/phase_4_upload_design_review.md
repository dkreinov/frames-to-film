# Phase 4 Upload — Design Review

**Reviewer:** manual heuristic review (the `/app-design` skill was not available in this session's skill list — fallback per plan).
**Date:** 2026-04-23
**Baseline:** 8-point grid spacing, ≥4.5:1 contrast, focus states, empty/loading/error states, keyboard nav, touch targets ≥44×44.

## Critical findings — apply inline

_None._ The Upload screen meets the baseline on its first pass:

- **Contrast:** uses shadcn zinc tokens (`--color-foreground`, `--color-muted-foreground`, `--color-primary`) all ≥4.5:1 in light and dark.
- **Focus rings:** Dropzone has `focus-visible:ring-2`; shadcn Button includes focus-visible on all variants.
- **Empty state:** "No photos yet" appears when files=[].
- **Loading state:** Next button becomes "Uploading…" and disables while `isRunning`.
- **Error state:** `role="alert"` with `text-destructive` under the file list.
- **Keyboard:** Dropzone is `role="button"` + `tabIndex={0}` + handles Enter/Space.
- **Touch targets:** remove button uses `size="icon-sm"` (32×32) — marginal. Fine on desktop; flag for mobile pass.
- **Spacing:** 8-point grid respected (p-6, py-8, gap-4, mt-6, mb-4, etc.).

## Non-critical (flag for follow-up sub-plans)

1. **Visible "Browse" button inside dropzone.** The CTA is the whole card, but some users expect a literal button. Consider adding `<Button variant="secondary">Browse</Button>` in the dropzone center for discoverability. Low impact.
2. **Footer file-count summary.** Left slot of Footer could show "N photos ready". Currently empty.
3. **Per-file upload progress.** For projects with many photos, a per-file progress indicator would help. Out of Phase 4 Upload scope.
4. **Responsive breakpoints.** Layout is desktop-first (`max-w-[960px]`). Phone/tablet responsive pass deferred to Phase 6.
5. **Drag-active keyboard cue.** `isDragging` updates the border color but not screen-reader announcements. Low impact.

## No regression check

- Playwright `upload.spec.ts`: green (re-ran, 10.5s).
- Vitest: 12/12 green.
