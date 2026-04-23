# Phase 4 Storyboard Screen — Design Notes

**Status:** Stitch timed out. Hand-designed against prose prompt below.

## Design prompt (would-have-been-sent)

Storyboard step 3 of 5 wizard. Auto-runs Extend on mount. Three states:

1. **Running (extend job)** — `JobProgressCard` from Prepare, headline
   "Building 16:9 frames…", subtext "Extending each photo to widescreen.
   This usually takes a minute for 10 photos."
2. **Done** — A drag-drop sortable grid of 16:9 thumbnails:
   - Each thumbnail is a `Card` with `aspect-video` content area
   - Position number badge top-left (1-indexed)
   - Drag-handle icon (`GripVertical`) top-right
   - Drag visual: card lifts (`shadow-lg`, slight rotate, opacity 0.8)
   - Drop visual: gap opens at insertion point
   - Save indicator at the top: "Order saved" → fades after 1s when
     debounced PUT /order resolves; "Saving…" while pending
3. **Error** — `JobProgressCard` error variant + Try again

**Tone:** still calm. The drag is the only "playful" interaction in
the whole app — keep it understated (no spring animations beyond the
default).

## Component inventory

| Component | Lives in | Notes |
|---|---|---|
| `SortableThumbnail` | `frontend/src/components/storyboard/SortableThumbnail.tsx` | wraps a thumbnail in `useSortable()` from @dnd-kit |
| `SortableGrid` | `frontend/src/components/storyboard/SortableGrid.tsx` | `DndContext` + `SortableContext` + map of SortableThumbnail; emits `onChange(newOrder)` |
| `useDebouncedSave` | `frontend/src/routes/useDebouncedSave.ts` | 300 ms debounce around `saveProjectOrder` |
| `JobProgressCard` | already in components/prepare/ | reuse |

## dnd-kit setup

```ts
const sensors = useSensors(
  useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
  useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
)
```

- PointerSensor with `distance: 4` so a click doesn't accidentally
  start a drag.
- KeyboardSensor for a11y baseline — Tab to a thumbnail, Space to
  pick up, Arrow keys to move, Space to drop.

## Polling pattern (reused from Prepare)

Same useQuery + refetchInterval + `startMutation.isError` derivation
that's frozen in `docs/design.md`.

## Page flow

1. Mount → `startExtend(projectId, 'mock')` → store `job_id`.
2. Poll `getJob` until done.
3. On done: call `listStageOutputs(projectId, 'kling_test')` →
   `names[]`. Also call `getProjectOrder(projectId)` — if non-null and
   the names match, use it as initial order.
4. Render `SortableGrid` with `names` as initial state.
5. On reorder: `useDebouncedSave` PUTs the new order (300 ms).
6. Footer Next button → `/projects/:id/generate`.

## Accessibility baseline

- KeyboardSensor wired (above).
- Each SortableThumbnail has `aria-label="Frame {n+1}, {filename}.
  Press space to pick up, arrow keys to move, space to drop."`
- A `role="status" aria-live="polite"` "Order saved" announcement when
  PUT resolves.

## Constraints flowing into later sub-plans

- `useDebouncedSave` is generic on `(value, delayMs, save)` — Generate
  / Settings can reuse for any debounced PUT.
- `SortableThumbnail` + `SortableGrid` are Storyboard-specific in name
  but generic in implementation; if Generate or Review needs sortable
  cards (e.g. drag winners into a takes-list), promote to
  `components/layout/`.
