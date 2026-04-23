# Phase 4 Sub-Plan 5 — Review & Export Screen (hand-design notes)

Stitch timed out on the single-attempt budget (5/5 sub-plans now —
pattern fully confirmed). Authoritative UX spec.

## Purpose

Step 5 of 5 in the wizard. Input: produced `seg_*.mp4` clips from
the Generate screen. Output: `full_movie.mp4` stitched + made
downloadable. Verdicts are advisory (persisted but don't gate
stitching in this sub-plan).

## Route

`/projects/:projectId/review` — lazy-loaded in `router.tsx`.

## Layout (desktop, 1280×720 target)

```
┌─ AppBar (Upload ✓ Prepare ✓ Storyboard ✓ Generate ✓ Review ●) ──┐
│                                                                  │
│  PageContainer                                                   │
│   ├─ Title "Review your clips and export"                        │
│   ├─ Subtitle "Watch each segment, mark it, then stitch."       │
│   │                                                              │
│   ├─ List of SegmentReviewRow cards (one per pair).              │
│   │                                                              │
│   ├─ (centered) StitchActionCard                                 │
│   │    ├─ idle:     [Stitch & Export] primary button             │
│   │    ├─ running:  spinner + "Stitching your full movie…"       │
│   │    ├─ error:    error banner + [Try again]                   │
│   │    └─ done:     [Download full movie] styled as anchor       │
│                                                                  │
└─ Footer                                                          │
   ├─ left: empty (Phase 6: "back to Generate")                    │
   └─ right: nothing — action is in the StitchActionCard above     │
```

## Per-segment row (`SegmentReviewRow`)

```
┌──────────────────────────────────────────────────────────────┐
│  ┌──────┐ → ┌──────┐   1_to_2   [▶ poster]                  │
│  │thumb │   │thumb │  (mono)   opens lightbox              │
│  │ a.jpg│   │ b.jpg│                                        │
│  └──────┘   └──────┘                                        │
│                                                              │
│  [ Winner ]  [ Redo ]  [ Bad ]      (toggle group)          │
└──────────────────────────────────────────────────────────────┘
```

- Thumbnails: `artifactUrl(projectId, 'kling_test', name)`, 96×54.
- Pair-key: `<code className="text-xs text-muted-foreground">1_to_2</code>`.
- Video poster: reuse `VideoLightbox` from Generate sub-plan —
  same aria-label format `Play {pair_key}`.
- Verdict buttons: 3 `<Button variant={selected ? 'default' : 'outline'}>`
  with `aria-pressed={selected}`. Selected verdict has filled bg;
  others have border-only.
- Row padding `p-4`, gap-4; gap-6 between rows.

## Stitch action card

Single card below all rows, centered `max-w-md`.

- **Idle**: `<Button size="lg">Stitch & Export</Button>`.
- **Running**: reuse `JobProgressCard` with headline
  "Stitching your full movie…", subhead "This usually takes a few
  seconds in mock mode.", `role="status"`.
- **Error**: `JobProgressCard` with status="error", headline
  "Stitching failed", retry button.
- **Done**: a single anchor styled like a primary button:
  ```tsx
  <a
    href={downloadUrl(projectId)}
    download
    className={buttonVariants({ variant: 'default', size: 'lg' })}
  >
    Download full movie
  </a>
  ```
  No extra fetch/blob — let the browser handle it via the
  existing `GET /download` endpoint's `Content-Disposition` header.

## State machine

1. On mount: `listStageOutputs('kling_test')`, `getProjectOrder`,
   `listVideos`, `listSegments`. Compute `pairKeys` from ordered
   outputs (same helper as Generate). For each pair with an
   existing video, render a `SegmentReviewRow`.
2. Seed local `verdicts: Record<seg_id, Verdict | null>` from
   `listSegments` result.
3. Click a verdict → `reviewSegment(pid, seg_id, verdict)`
   mutation. Update local state **only on success** (no
   optimistic-then-rollback). Failed POST leaves the previous
   selection unchanged; the next test asserts this.
4. Click "Stitch & Export" → `startStitch(pid, 'mock')` →
   `jobId` set → poll `getJob` with the frozen pattern.
5. On stitch `done`: swap button for anchor.

## Copy strings

| State | Copy |
|---|---|
| title | Review your clips and export |
| subtitle | Watch each segment, mark it, and then stitch the full movie. |
| verdict aria-label | "Mark {pairKey} as {verdict}" |
| stitch idle button | Stitch & Export |
| stitch running head | Stitching your full movie… |
| stitch running sub | Usually a few seconds in mock mode. |
| stitch error head | Stitching failed |
| stitch error sub | Check the backend, then try again. |
| stitch done anchor | Download full movie |

## Accessibility

- Each verdict button: `aria-pressed={verdict === thisButton}`,
  `aria-label="Mark {pairKey} as {verdict}"`. Keyboard: native
  button, Space/Enter activate.
- Stitch card: `role="status"` while running, `role="alert"` on
  error — same convention as `JobProgressCard`.
- Download anchor: visible text "Download full movie"; browser
  announces it as a link.
- Focus order: rows top-to-bottom, then Stitch button, then
  Download anchor (after done).

## Non-goals (this sub-plan)

- No per-pair "Redo this pair" trigger (Q1=A; belongs in Phase 6).
- No notes field on rows (back-end accepts them; keep UI tight).
- No partial-stitch (winners-only) — verdicts are advisory.
- No preview of `full_movie.mp4` in the screen — user downloads.
- No responsive mobile layout.
