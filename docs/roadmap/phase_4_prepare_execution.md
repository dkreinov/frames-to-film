# Phase 4 — Prepare Sub-Plan Execution Log

**Sub-plan:** 2 of 5 (Prepare) — after Upload, before Storyboard.
**Status:** done
**Plan:** `plans/plan-20260423-1722.md` (self-deleted on close-out)
**Dates:** 2026-04-23

## Outcome

Prepare screen fully wired. Auto-posts `/prepare` on mount, polls
`/jobs` every 2 s via TanStack Query, switches to an `OutputsGrid` of
outpainted thumbnails when the job lands in `done`. New backend
endpoint `GET /projects/{id}/outputs/{stage}` introduced to list files
by name.

- 83/1 backend regression (up from 79; +4 outputs tests).
- 22/22 vitest (up from 12; +4 Prepare unit + 3 Prepare integration +
  3 new api client).
- 4/4 Playwright (upload + upload.golden + prepare + prepare.golden).
- 4 golden PNGs tracked (Upload's 2 recovered + Prepare's 2).

## Frozen contracts introduced

- `GET /projects/{id}/outputs/{stage}` returns
  `{stage: string, outputs: string[]}`. Sorted; regular files only; no
  recursion; path-escape guarded.
- `frontend/src/api/client.ts` adds `startPrepare`,
  `listStageOutputs`, `artifactUrl`.
- Polling pattern lifted into `docs/design.md` "Frozen contracts"
  section. Storyboard / Generate / Review sub-plans must use it
  verbatim (including the `startMutation.isError` branch — advisor
  caught its absence as a stranded-spinner bug).
- `JobProgressCard` (accepts `status`, `headline`, `subheadline`,
  `errorText?`, `onRetry?`) + `OutputsGrid` (accepts `projectId`,
  `stage`, `names[]`, `altPrefix?`). Both generic; later sub-plans
  reuse rather than fork.

## Decisions taken autonomously

- Auto-trigger `POST /prepare` on mount (no Start button).
- Hardcoded `mock` mode; Settings sub-plan exposes the api toggle.
- Stitch: 1 attempt per the Upload-lesson budget; timed out as
  predicted; fell back to hand-design.

## Advisor findings (2026-04-23 close-out)

### Resolved inline

1. **Start-mutation error stranded the user on the spinner.** If
   `POST /prepare` 5xx'd, `jobId` stayed null, `jobQuery` stayed
   disabled, `status` stuck at `'pending'` forever, no retry button.
   Fixed with `startMutation.isError ? 'error' : jobQuery.data?.status`
   and a dedicated integration test (`surfaces POST /prepare 5xx to
   the error card`) pins the regression.

2. **`.gitignore` silently swallowed goldens.** Upload sub-plan's
   "Step 9 commit" shipped with zero PNGs tracked (`*.png` rule). Fix:
   `!docs/design/golden/**` exception + `git ls-files` verification
   step. Upload's 2 goldens recovered into this sub-plan's commit.

### Flagged for follow-up sub-plans

1. **`BackendStatus` renders in production.** It's dev-only by intent
   but always mounts. Phase 6 should gate with `import.meta.env.DEV`.
2. **No per-file progress indicator.** Running state is an opaque
   spinner. Phase 6 or a Prepare v2 can add `<progress>` when the
   backend emits partial status.
3. **Thumbnail order is file-name sorted.** Good for mock; real
   Prepare should preserve upload order. Phase 6 polish.
4. **No "back to Upload" text link in Footer.** Add consistently across
   all 5 wizard screens — deferred so it lands everywhere at once.

## Findings for sub-plans 3-5

1. **One Stitch attempt per screen.** Confirmed pattern: 1 fast call,
   immediate hand-design fallback. Don't burn retries.
2. **BackendStatus positioning: `bottom-[84px] right-3` + z-20 +
   `pointer-events-none`.** Without the last flag, it intercepts
   clicks on the Footer's Next button. This pattern shouldn't need
   re-discovering.
3. **`startMutation.isError` branch in the status derivation is
   mandatory.** Baked into `docs/design.md` polling pattern. Don't
   copy-paste the useQuery without it.
4. **`OutputsGrid` / `JobProgressCard` are genuinely generic.** Import
   from `components/prepare/` (the name is fine for now; later
   sub-plans can move to `components/layout/` if >2 consumers exist).
5. **Goldens go in `docs/design/golden/` and the gitignore now has an
   exception.** After `git add`, verify with `git ls-files` that they
   actually landed.

## Follow-ups that don't belong to any sub-plan

- Phase 6 `import.meta.env.DEV` gate for BackendStatus.
- Phase 6 responsive breakpoints pass (desktop-only today).
