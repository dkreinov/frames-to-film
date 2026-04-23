# Phase 4 Prepare Screen — Design Notes

**Status:** Stitch timed out on 1 attempt (see `phase_4_prepare_stitch.json`).
Hand-designed against the prose prompt below using shadcn primitives.
This document is the design-of-record for Step 5.

## Design prompt (would-have-been-sent to Stitch)

A "Prepare Photos" screen that's step 2 of the 5-step wizard. Runs the
4:3 normalize stage automatically on mount. Three states:

1. **Running** — A centered card with:
   - Rounded-2xl card surface, ~420px wide, py-8 px-6
   - `Loader2` spinner from `lucide-react` (h-6 w-6, animate-spin)
   - Heading: "Preparing photos…"
   - Subtext: "Normalizing to 4:3 landscape. This usually takes a minute for 10 photos."
   - No progress bar (the backend doesn't emit percent today)

2. **Done** — A responsive grid of thumbnails of the outpainted photos:
   - Each thumbnail is a rounded-xl card with `aspect-[4/3]`, object-cover
   - Grid: `grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4`
   - Above the grid: small caption "Prepared N photos" in muted text
   - Footer "Next: Storyboard" primary button becomes enabled

3. **Error** — A card with:
   - `AlertTriangle` icon (destructive color, h-6 w-6)
   - "Preparation failed"
   - Muted subtext showing the first line of the backend error
   - A `Button variant="outline"` "Try again" that re-POSTs /prepare

## Component inventory

| Component | Lives in | Notes |
|---|---|---|
| `JobProgressCard` | `frontend/src/components/prepare/JobProgressCard.tsx` | renders states 1 + 3 of the job polling cycle |
| `OutputsGrid` | `frontend/src/components/prepare/OutputsGrid.tsx` | reusable — Storyboard + Review sub-plans will consume it with different stage names |
| Shared: `AppBar`, `PageContainer`, `Footer` | already in `layout/` | reuse |
| Shared: `Button`, `Card` | already in `ui/` | reuse |

## Polling pattern (frozen contract for future sub-plans)

```tsx
const { data: job } = useQuery({
  queryKey: ['job', projectId, jobId],
  queryFn: () => getJob(projectId, jobId),
  enabled: !!jobId,
  refetchInterval: (q) =>
    q.state.data?.status === 'done' || q.state.data?.status === 'error'
      ? false
      : 2000,
})
```

Once `job.status === 'done'`, fetch `listStageOutputs(projectId,
'outpainted')` and render the grid from `artifactUrl(...)` entries.

## Page flow

1. Component mounts. Read `projectId` from the route param.
2. Fire `useMutation` to `startPrepare(projectId, 'mock')`. Store returned `job_id`.
3. Poll job until `done` or `error`.
4. On `done`, fetch outputs list.
5. Render grid.
6. Footer Next button → `/projects/:id/storyboard`.

## Accessibility baseline

- Spinner wrapped in `role="status"` with `aria-live="polite"` so SR
  users hear when the state changes.
- Error card uses `role="alert"`.
- Each thumbnail `<img>` has `alt="outpainted photo {N}"` (ok for now;
  Phase 6 can enhance with source-filename reverse lookup).

## Constraints that flow into later sub-plans

- `OutputsGrid` stays generic — takes `(projectId, stage, names[])` so
  Storyboard and Review can swap `outpainted` for `kling_test` /
  `kling_test/videos` without forking the component.
- `JobProgressCard` also stays generic (`headline`, `subheadline`,
  `error?`) so Generate / Stitch reuse it.
