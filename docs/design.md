# olga_movie Frontend Design System

**Status:** authoritative design source for Phase 4 and later sub-plans.
**Last updated:** 2026-04-23

This doc pins the visual / interaction / component contracts for the
React frontend at `frontend/`. Every sub-plan (Upload, Prepare,
Storyboard, Generate, Review+Export, Settings) reuses these primitives.
Deviations require updating this doc first.

## Stitch integration status

Each sub-plan attempts to generate its screen via StitchMCP
(`mcp__StitchMCP__generate_screen_from_text`) first, then translates the
result into shadcn React. When Stitch times out (known: first three
Upload-screen attempts all hit the MCP timeout despite the service being
reachable — see `docs/design/phase_4_upload_stitch.json`), the fallback
is the prose design prompt captured in the sub-plan's
`phase_4_<screen>_notes.md` — that prompt is the design-of-record.

**Stitch project:** `projects/10276889797068420736` (title: *olga_movie
Phase 4 Frontend*). Future sub-plans reuse the same project ID so all
screens sit side-by-side in the Stitch dashboard when generation
eventually succeeds.

## Product principles

1. **Calm and serious.** The user is handling their family memories.
   No playfulness, no gradients, no sparkles, no loud colors.
2. **Trustworthy.** Every surface should feel like it respects the
   user's original photos — no cutesy icons on destructive actions,
   no surprise animations, clear copy ("We'll preserve every face
   exactly").
3. **Reversible.** Actions that take more than a second show progress
   and can be cancelled or re-run. Deletion always confirms.
4. **Offline-friendly.** The whole UI runs against mock mode with zero
   API cost. Production mode is just a knob.

## Visual tokens (Tailwind v4 `@theme`)

Defined in `frontend/src/index.css`. Tokens use OKLCH for future-proof
colour-space behaviour. Both light and dark themes use the same token
names — the dark override block in `src/index.css` remaps them.

| Token | Light | Purpose |
|---|---|---|
| `--color-background` | near-white (`oklch(1 0 0)`) | page body |
| `--color-foreground` | near-black (`oklch(0.141 ...)`) | primary text |
| `--color-card` | white | card surface |
| `--color-card-foreground` | near-black | text on cards |
| `--color-primary` | zinc-900-ish | primary button background |
| `--color-primary-foreground` | near-white | primary button text |
| `--color-muted` | zinc-100 | secondary surfaces |
| `--color-muted-foreground` | zinc-500 | secondary text |
| `--color-accent` | zinc-100 | hover/active subtle surfaces |
| `--color-destructive` | red-ish | delete/error |
| `--color-border` | zinc-200 | hairline rules, dashed dropzone |
| `--color-input` | zinc-200 | input background border |
| `--color-ring` | zinc-400 | focus ring |
| `--radius` | `0.625rem` | standard border radius |

No opinionated typography beyond system font stack. Heading weights
stop at 600.

## Layout

- Page container is always `max-w-[960px] mx-auto px-6`.
- App bar is 64px tall, full width, bottom-border hairline.
- Footer CTA bar is 72px tall, full width, top-border hairline.
- Main content area sits between the two, scrolls.

## Wizard flow

Five steps, in order:

1. **Upload** — `/projects/new/upload` + `/projects/:id/upload`
2. **Prepare** — `/projects/:id/prepare`
3. **Storyboard** — `/projects/:id/storyboard`
4. **Generate** — `/projects/:id/generate`
5. **Review & Export** — `/projects/:id/review`

Plus a non-wizard **Settings** screen: `/settings`.

Each wizard screen has: app bar (with stepper), heading + subtitle,
content area, footer CTA. The CTA is always a primary "Next: <name>"
button right-aligned. Back navigation uses a subtle text link on the
left of the footer.

## Shared components (in `frontend/src/components/layout/`)

- **`AppBar`** — left: logo mark + "olga_movie"; center: `<WizardStepper />`; right: settings gear `Link` to `/settings`.
- **`WizardStepper`** — 5 dots with labels, current step highlighted with `aria-current="step"`. Completed steps have a checkmark; future steps are muted.
- **`Footer`** — slot-style container. Left slot = back link (optional); right slot = primary CTA.
- **`PageContainer`** — `max-w-[960px] mx-auto px-6 py-8` wrapper with optional heading + subtitle props.

## Per-screen components

### Upload screen (Phase 4, sub-plan 1)

- `DropzoneCard` — dashed border, `onDrop` + click-to-browse hidden
  `<input type="file" multiple accept="image/png,image/jpeg,image/webp">`.
  Accessibility: `role="button"`, keyboard Enter/Space opens picker.
- `UploadedFilesList` — list of rows; each: 48×48 thumbnail (object
  URL), filename (truncate-1), filesize (human-readable), remove (×).
  Empty state: centered muted "No photos yet" line.

### Prepare screen (future sub-plan)

- Runs `POST /projects/{id}/prepare` in mock mode by default.
- Shows a progress card polling `GET /jobs/{id}` every 2s.
- Shows the resulting `outpainted/*.jpg` thumbnails once done.

### Storyboard screen (future sub-plan)

- Uses `@dnd-kit/core` + `@dnd-kit/sortable` for drag-drop ordering.
- Shows `outpainted/*.jpg` as a horizontal/grid scroll of cards.
- "Regenerate" button per card, triggers a focused retry.

### Generate screen (future sub-plan)

- Per-pair cards with prompt preview (pulled from `/prompts`).
- Style preset selector (cinematic / nostalgic / vintage / playful).
- Bulk "Generate all" + per-pair "Generate this".

### Review & Export screen (future sub-plan)

- Per-segment video players.
- Winner/redo/bad buttons (posts to `/review`).
- "Download full movie" at bottom once `/stitch` is done.

### Settings screen (future sub-plan)

- API key inputs stored in `localStorage` only — never sent to the
  backend. Three keys: `GEMINI_KEY`, `KLING_ACCESS_KEY`,
  `KLING_SECRET_KEY`. Request interceptor in `frontend/src/api/client.ts`
  attaches them as headers if present.
- "Clear keys" button.
- `GENERATION_MODE` toggle (mock | api).

## Data layer

- **`@tanstack/react-query`** for server state. Query keys are
  `['projects']`, `['project', id]`, `['uploads', projectId]`, etc.
- **React useState** for local UI state.
- **No Zustand / Jotai / Redux.** The app's state needs don't warrant
  another layer.

## Accessibility baseline

- All interactive elements reachable via keyboard.
- Focus ring uses `--color-ring`.
- Contrast ≥ 4.5:1 on `--color-foreground` vs `--color-background` and
  on `--color-muted-foreground` vs `--color-muted`.
- Drag-drop regions have a keyboard equivalent (click-to-browse).
- Live regions on job-status polling updates.

## Testing contract

Each sub-plan must produce:

1. Vitest unit tests for components (render, interactions).
2. Vitest integration tests for API mutations via MSW.
3. Playwright E2E for the happy path against a live uvicorn + vite.
4. `/app-design` skill pass with critical findings applied inline.
5. Claude-in-Chrome golden screenshot saved under
   `docs/design/golden/phase_4_<screen>.{gif,png}`.

When `/app-design` is unavailable, a manual heuristic review covers:
8-point grid spacing, ≥4.5:1 contrast, focus states, empty states,
loading states, error states.

## Frozen contracts (Phase 4 downstream)

These cannot change without updating every later sub-plan:

- Visual tokens in `frontend/src/index.css` `@theme` block.
- Route tree in `frontend/src/routes/router.tsx`.
- `frontend/src/api/client.ts` function signatures + types from
  `frontend/src/api/types.ts`.
- Shared layout components in `frontend/src/components/layout/`.
- Wizard ordering (Upload → Prepare → Storyboard → Generate → Review).
- **Stage-job polling pattern** (introduced by Prepare sub-plan):

  ```ts
  const jobQuery = useQuery({
    queryKey: ['job', projectId, jobId],
    queryFn: () => getJob(projectId, jobId!),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'done' || s === 'error' ? false : 2000
    },
  })

  // Surface POST-side errors too — otherwise the spinner stalls forever:
  const status: 'pending' | 'running' | 'done' | 'error' =
    startMutation.isError ? 'error' : (jobQuery.data?.status ?? 'pending')
  ```

  Every wizard screen that drives a `POST /stage` + polls
  `GET /jobs/{id}` MUST use this exact pattern. The
  `startMutation.isError` branch is not optional — without it, a 5xx on
  the initial POST strands the user on the spinner.
- **Generic reusable components** (introduced by Prepare sub-plan):
  `JobProgressCard` + `OutputsGrid` under
  `frontend/src/components/prepare/`. Storyboard / Generate / Review
  sub-plans SHOULD consume these with different props instead of
  forking. Move them to `components/layout/` if any of those screens
  actually need them — for now the name is fine.

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-04-23 | StitchMCP as first-pass generator with hand-design fallback | Stitch service timed out 3× on Upload prompt; hand-design unblocks the sub-plan while preserving Stitch project for later attempts. |
| 2026-04-23 | Tailwind v4 with `@theme` (no `tailwind.config.ts`) | v4 native CSS theming; simpler build; matches shadcn's move to v4. |
| 2026-04-23 | React Router (not Next.js / Remix) | Single-page wizard; no SSR needed; smaller dep footprint. |
| 2026-04-23 | TanStack Query only (no Zustand) | All state is server-owned; local state fits `useState`. |
| 2026-04-23 | Shadcn "new-york" style, zinc base | Most neutral; suits the "calm and serious" principle. |
| 2026-04-23 | pnpm preferred, npm fallback | pnpm faster; npm available on Windows PATH. Phase 4 shipped on npm because pnpm was not on PATH — document over reinstall. |
| 2026-04-23 | `OLGA_PYTHON` env var overrides Playwright's `python` command | Windows dev may have Python installed outside PATH; playwright.config.ts falls back to `process.env.OLGA_PYTHON ?? 'python'`. |
