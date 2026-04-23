# Phase 4 Generate — Design Review

**Reviewer:** advisor pre-close-out + manual heuristic pass.
**Date:** 2026-04-23
**Baseline:** 8-point grid, ≥4.5:1 contrast, focus states,
empty/loading/error states, keyboard nav, touch targets ≥44×44.

## Critical findings — addressed inline

1. **Initial-load "Saved" pill flashed on the loading screen.**
   `<p role="status">{isSaving ? 'Saving…' : 'Saved'}</p>` rendered
   unconditionally while the prompts-loading spinner was up, so a
   brand-new project momentarily announced "Saved" before anything
   had been saved. Gated on `prompts !== null` so the pill only
   mounts once there is a local map to save.

2. **Prompts-drift auto-regen infinite-loop risk.** `regenAttempted`
   ref guard — at most one auto-regen per mount. If the second GET
   after regen still has mismatched keys, surface an error card
   ("Couldn't write prompts") with a reload CTA. Covered by unit
   test `triggers one re-gen when server prompts keys do not match`.

3. **Debounced-save echo regression.** Identical risk to the
   Storyboard sub-plan — `useDebouncedSave<Record<string,string>>`
   would otherwise fire a PUT on the initial null-to-map transition.
   `skipNextNonNull` guard applies; integration test `auto-generates
   prompts when missing, then renders editable rows with no PUT
   echo` pins it.

## Checklist pass

- **Contrast:** shadcn zinc tokens throughout. Textarea uses
  `border-input` + `focus-visible:ring-[3px]` for ≥4.5:1 with focus.
- **Focus rings:** Textarea, Generate/Next buttons, and
  VideoLightbox trigger all have visible rings.
- **Empty / loading / error:** four primary states
  (prompts-loading, prompts-error aka "Couldn't write prompts",
  generate-running, generate-error) all reuse `JobProgressCard`
  with `role="status"` / `role="alert"` as applicable.
- **Keyboard:** textarea is native, tab-focusable. Dialog focus-trap
  handled by Radix. Close via Escape.
- **Touch targets:** Generate/Next buttons `size="lg"` (40px).
  VideoLightbox poster is `h-14 w-24` (56×96); click area is larger
  than 44×44.
- **8-point grid:** `space-y-3`, `p-4`, `space-y-6`, `gap-3`, `mb-3`.
- **SR live region:** Saving/Saved pill is `role="status"
  aria-live="polite"`. Now gated on `prompts !== null` so it doesn't
  lie on the loading screen.

## Frozen-contract drift (flag for unification)

- **`generateStatus` enum shape.** The Prepare/Storyboard frozen
  pattern derives a 4-state status as
  `startMutation.isError ? 'error' : (jobQuery.data?.status ?? 'pending')`.
  GenerateScreen uses a 4-state `'idle' | 'running' | 'done' | 'error'`
  because the Generate job does NOT auto-start — it requires an
  explicit click — so the initial state is `'idle'` rather than
  `'pending'`. This is a *deliberate* divergence, not a bug: copying
  the Prepare pattern would make the screen permanently "pending"
  until a click. Review + Settings sub-plans that have an auto-start
  flow should keep the original shape; anything user-triggered
  should mirror Generate.

## Non-critical (flagged for follow-up sub-plans / Phase 6)

1. **`regenFailed` reads a ref during render.** `regenAttempted.current`
   is read inline in the `regenFailed` derivation. This works because
   other state changes (`promptsJobQuery.data`, `promptsQuery.data`)
   re-render the component around the same time the ref transitions.
   Brittle — if a future refactor decouples those, regenFailed could
   go stale. Cleaner: `useState<boolean>(false)` for the "auto-regen
   was attempted" signal. Flag for Phase 6.
2. **Saving pill has no error feedback.** A 5xx on `PUT /prompts`
   silently clears `isPending`. Same pattern carried forward from
   Storyboard; Phase 6 polish should add toast/rollback across
   every `useDebouncedSave` caller, not just this one.
3. **dnd-kit bundle already present** (from Storyboard), so adding
   Radix Dialog here is a modest bump (~15 KB gz). No concerns for
   desktop; revisit if mobile polish demands stricter caps.
4. **`prompts.json` orphan keys after reorder** — documented in
   Storyboard review; still unresolved. `resolve_prompt` ignores
   them so the artifact grows but nothing breaks. Phase 6 cleanup
   pass should trim keys to the current pair sequence on the next
   PUT.
5. **Prompts auto-regen doesn't tell the user why.** If the user
   reorders frames in Storyboard and comes back to Generate,
   "Writing starter prompts…" appears again with no explanation.
   Phase 6 copy polish: "Frames changed since last render — writing
   fresh prompts…" when the trigger is a drift rather than first-run.
