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
    refetchIntervalInBackground: true,
  })

  // Surface POST-side errors too — otherwise the spinner stalls forever:
  const status: 'pending' | 'running' | 'done' | 'error' =
    startMutation.isError ? 'error' : (jobQuery.data?.status ?? 'pending')
  ```

  Every wizard screen that drives a `POST /stage` + polls
  `GET /jobs/{id}` MUST use this exact pattern. Two options are not
  optional:
  - `startMutation.isError` branch — without it, a 5xx on the initial
    POST strands the user on the spinner.
  - `refetchIntervalInBackground: true` — TanStack Query defaults to
    `false`, which silently pauses polling whenever the browser tab
    loses visibility (Chrome's own throttling, user switching tabs,
    any extension or tool that opens the tab as `document.hidden`).
    Setting this to `true` keeps `GET /jobs/{id}` firing so when the
    user returns, the spinner isn't stalled on a stale payload. The
    bandwidth cost is trivial (one `GET` every 500–2000ms only for
    the duration a job is actually running).
- **Generic reusable components** (introduced by Prepare sub-plan):
  `JobProgressCard` + `OutputsGrid` under
  `frontend/src/components/prepare/`. Storyboard / Generate / Review
  sub-plans SHOULD consume these with different props instead of
  forking. Move them to `components/layout/` if any of those screens
  actually need them — for now the name is fine.
- **Frame ordering precedence** (introduced by Storyboard sub-plan).
  All downstream stages that consume `<project>/kling_test/*.jpg` MUST
  honour the user's saved Storyboard order if present:

  1. If `<project>/order.json` exists and is `{order: string[]}`,
     filter to filenames that still exist on disk and use that.
  2. Otherwise fall back to numeric-prefix sort (`_sort_key`).

  Implemented in `backend/services/generate.py::_ordered_frames` and in
  `generate_all_videos.py` via the `PROJECT_ORDER` global swapped under
  `_RUN_LOCK` (mirrors `PROJECT_PROMPTS`). Stitch / Review sub-plans
  must reuse `_ordered_frames` rather than re-globbing.
- **Drag-and-drop pattern** (introduced by Storyboard sub-plan).
  `@dnd-kit/core + /sortable + /utilities` with
  `PointerSensor({ activationConstraint: { distance: 4 } })` +
  `KeyboardSensor`, `SortableContext` with `rectSortingStrategy`, and
  `arrayMove` on `onDragEnd`. Per-item drag handles must carry an
  `aria-label` matching `/^Drag frame \d+ \(.+\)\./` so Playwright +
  Testing Library can target them by role+name. Any future sortable
  surface (Review re-order, Settings) reuses these primitives instead
  of re-picking a DnD library.
- **`useDebouncedSave` hook** (introduced by Storyboard sub-plan,
  `frontend/src/routes/useDebouncedSave.ts`). Signature
  `useDebouncedSave<T>(value: T | null, delayMs, save)`. Skips entirely
  while `value === null`; uses a `skipNextNonNull` ref to drop the
  first non-null transition (the server-load echo) so the initial seed
  never PUTs back. Verified safe under React `<StrictMode>` by
  integration test. Generate / Review must use this exact hook for any
  debounced PUT instead of rolling their own.
- **`PUT/GET /projects/{id}/order`** (introduced by Storyboard
  sub-plan). Body: `{order: string[]}` (non-empty, all strings).
  Persists to `<project>/order.json`. `GET` returns 404 before first
  PUT (front-end translates to `null`). Owner-scoped (404 if the
  project belongs to another `user_id`). No legacy fallback —
  consumers must accept the 404 → null mapping.
- **Prompts/pair-key precedence** (introduced by Generate sub-plan).
  `_pair_keys_for_project(project_dir)` in
  `backend/services/prompts.py` honours `<project>/order.json` the
  same way `_ordered_frames` does. Any backend code that enumerates
  pairs MUST call this helper, never re-glob. Leftover keys in
  `prompts.json` from a prior ordering are harmless —
  `resolve_prompt` ignores unknown keys and falls back to the style
  preset. Trim-on-PUT is a Phase 6 cleanup, not a required contract.
- **`PUT/GET /projects/{id}/prompts`** (introduced by Generate
  sub-plan). PUT body `{prompts: {[pair_key]: string}}` (non-empty,
  all string values). Full-file atomic replace via tempfile +
  `os.replace`. Owner-scoped. GET returns the stored map or 404
  (front-end translates to `null`). No per-key PATCH endpoint —
  callers PUT the whole map.
- **`GET /projects/{id}/videos`** (introduced by Generate sub-plan).
  Returns `{videos: [{name: string, pair_key: string}]}` in the
  sequence implied by `_ordered_frames`. Empty list when
  `kling_test/videos/` is missing. The UI pairs each item with a
  `PromptRow` via `pair_key`.
- **Radix Dialog primitive** (introduced by Generate sub-plan) —
  `components/ui/dialog.tsx` wraps `radix-ui`'s Dialog with the
  project's zinc tokens. Any future modal/lightbox in Review /
  Settings MUST reuse this file rather than importing Radix
  directly or forking a second dialog component.
- **`regenAttempted` single-shot ref pattern** (introduced by
  Generate sub-plan). For any screen that auto-reconciles server
  state on mount (re-run a stage when inputs drift), use a
  `useRef(false)` guard + an explicit error branch for the second
  failure, not a loop. Pattern proven in
  `GenerateScreen.tsx`; covered by the "triggers one re-gen"
  unit test.
- **`generateStatus` 4-state variant** (introduced by Generate
  sub-plan). User-triggered stage screens use
  `'idle' | 'running' | 'done' | 'error'` — NOT the auto-start
  pattern's `'pending'`. Review / Settings must pick the shape
  that matches whether the stage auto-starts; don't mix.
- **`GET /projects/{id}/segments`** (introduced by Review sub-plan).
  Returns `{segments: [{seg_id, verdict, notes, updated_at}]}`
  sorted by `seg_id`. Empty list when no reviews exist (200, not
  404). Owner-scoped.
- **`seg_id` canonical form** (introduced by Review sub-plan):
  `seg_<pair_key>`, e.g. `seg_1_to_2`. Matches the produced video
  filename stem. Review's POST/GET, and anything future that
  touches segments, MUST use this form.
- **Verdict POST-then-update pattern** (introduced by Review
  sub-plan). Local verdict state updates ONLY inside
  `mutation.onSuccess`. Rejections leave the UI unchanged — no
  optimistic-then-rollback. Prevents phantom verdicts on 5xx.
  Required test: a mutation that rejects + asserts
  `aria-pressed` stays false.
- **`setState`-during-render seed-once pattern** (introduced by
  Review sub-plan). For "seed local state once from a server query,
  never again" workflows, use:
  ```tsx
  const [seeded, setSeeded] = useState(false)
  if (!seeded && query.data) {
    setLocal(derive(query.data))
    setSeeded(true)
  }
  ```
  REQUIRED: a regression test that calls
  `qc.refetchQueries({ queryKey })`, awaits the mock to be called
  a second time, and asserts local state survives the refetch.
  Without that harness, a future refactor to `useEffect` with
  wrong deps can silently regress.
- **Download-via-`<a href download>`** (introduced by Review
  sub-plan). For one-shot file downloads, use a plain anchor
  styled with `buttonVariants({variant:'default', size:'lg'})`
  pointing at a backend URL that sets `Content-Disposition`. Do
  NOT wrap in `<Button>` + blob fetch unless a progress overlay
  or filename override is required.
- **`useSettings` hook + localStorage schema** (introduced by
  Settings sub-plan, `frontend/src/routes/useSettings.ts`).
  Two storage keys, both JSON-encoded:
  - `olga.keys` — `{gemini: string}` (more keys in Phase 5).
    Empty string means "not set"; components MUST treat "" as
    absent, not as a valid key.
  - `olga.modes` — `{prepare, extend, generatePrompts,
    generateVideos, stitch: 'mock' | 'api'}`. Default all `mock`.
  The hook exposes `{keys, modes, setKey, clearKey, setMode}`
  and listens for cross-tab `storage` events so a key saved in
  one tab propagates to others without reload. Any future
  per-user preference that needs to survive reload but not
  leave the browser belongs here — do NOT roll a second
  localStorage wrapper.
- **`X-Gemini-Key` header attach pattern** (introduced by
  Settings sub-plan). `frontend/src/api/client.ts` exports an
  internal `apiFetch(url, init)` wrapper that reads
  `localStorage['olga.keys'].gemini` at call time and attaches
  it as the `X-Gemini-Key` request header when non-empty. Every
  client function MUST go through `apiFetch` — never call
  `fetch` directly — so new endpoints inherit the header for
  free. The key is read on each call (not cached) so a Save in
  Settings takes effect on the very next request without a
  React re-render.
- **`resolve_gemini_key` backend utility** (introduced by
  Settings sub-plan, `backend/deps.py`). Not a FastAPI
  `Depends` — handlers call it only on `mode == "api"`
  branches so mock-mode requests never require a key.
  Precedence: request header `X-Gemini-Key` → env var
  `gemini` → `HTTPException(400, "Gemini API key required for
  api mode. Paste a key in Settings or set the 'gemini' env
  var.")`. Any future per-user-provided secret (Kling,
  OpenAI, etc.) follows the same shape: a `resolve_<vendor>_key`
  in `deps.py` + a matching `X-<Vendor>-Key` header attached
  by `apiFetch`. Do NOT add a blanket `Depends(resolve_*)` —
  mock mode would then 400 without a key, defeating the
  "runs offline for free" principle.
- **Mode propagation via `useSettings`** (introduced by
  Settings sub-plan). Every wizard screen that starts a stage
  job MUST read `modes.<stageKey>` from `useSettings()` and
  pass it to the `startStage` mutationFn. The mutationFn MUST
  accept the mode as an explicit argument — do NOT hardcode
  `'mock'` in the mutationFn or the Settings toggle becomes
  decorative. Required test (proven in `PrepareScreen.test.tsx`
  and `GenerateScreen.test.tsx`): seed `localStorage['olga.modes']`
  with the stage set to `'api'` before mount, then assert the
  client mock was called with `'api'`. A passing test that
  calls the mock directly is a placebo and MUST be rewritten
  to drive the real mount path.
- **Non-wizard `AppBar`** (introduced by Settings sub-plan).
  `AppBar`'s `currentStep` prop is optional. Wizard routes pass
  their step id; non-wizard routes (Settings, any future
  admin/help page) render `<AppBar />` with no prop so
  `WizardStepper` highlights nothing. Do NOT pass a fake step
  id just to satisfy the type — it lies to the user.
- **`Mode` type** (introduced by Phase 5 Sub-Plan 1). `Mode =
  'mock' | 'api' | 'web'`. `web` applies ONLY to `generateVideos`
  today; all other stages render a blank cell in the Settings
  web column so the UI never tempts the user to flip a
  nonsensical mode. api/client.ts stage-start signatures are
  widened to accept `Mode` on all five stage starters to keep
  TypeScript clean — the per-stage UI gates, plus backend
  `Literal` validation at each router, prevent an invalid
  combination from reaching a runner.
- **`VeoWebAdapter` interface** (introduced by Phase 5 Sub-Plan
  1, `backend/adapters/veo_web.py`). Methods: `authenticate()`,
  `upload_frame(path)`, `request_generation(frame_a_url,
  frame_b_url, prompt)`, `download_clip(job_ref)`, `cleanup()`.
  All raise `WebModeNotImplemented` (a `NotImplementedError`
  subclass) until Phase 5 Sub-Plan 2 wires them against a real
  Playwright/Chrome-profile session. Method names + signatures
  are frozen — Sub-Plan 2 MUST NOT rename. Class is also a
  context manager so `cleanup()` runs on failure paths.
- **`WebModeNotImplemented` sentinel** (introduced by Phase 5
  Sub-Plan 1). `generate_runner`'s `mode == 'web'` branch
  catches ONLY this sentinel and re-raises as a `RuntimeError`
  with a user-facing message ("Phase 5 Sub-Plan 2 —
  authenticated browser profile required. Flip 'Generate
  videos' to api or mock mode in Settings."). `jobs.run_job_sync`
  records that as `status='error'/error=<msg>`. Any future
  adapter that follows the same "stub-first, implement-later"
  pattern MUST reuse this sentinel shape — bare
  `NotImplementedError` leaks the traceback.
- **`STAGE_ROWS` shape for Settings** (introduced by Phase 5
  Sub-Plan 1). Each row declares `apiEnabled: boolean` and
  `supportsWeb: boolean`. `apiEnabled=false` disables the api
  radio with an "api mode arrives in Phase 5" note;
  `supportsWeb=true` renders a web radio (disabled until
  Sub-Plan 2) with an inline "web mode arrives in Phase 5
  Sub-Plan 2" note. `supportsWeb=false` renders a blank web
  cell. Any future mode (e.g., a hypothetical `'kling'`) plugs
  in by adding another per-row boolean + column header — do
  NOT retrofit a general `supportedModes: Mode[]` array until a
  third enabled-today vendor materialises.

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
| 2026-04-24 | Settings: localStorage + `X-Gemini-Key` header, per-stage mode toggles | User-supplied secrets belong on the client — never in the backend `.env` of a tool others will run. Per-stage toggle is the minimum knob that scales to Phase 5 (Kling web mode) without redesigning Settings. |
| 2026-04-24 | Only `generatePrompts` api-mode enabled in Settings; other stages gated until Phase 5 | Shipping `api` radios disabled-with-note is clearer than hiding them: user sees the roadmap, understands why, won't file "toggle does nothing" bugs. Phase 5 flips them on one by one as each vendor path lands. |
| 2026-04-24 | Phase 5 split into Sub-Plan 1 (scaffolding, autonomous-safe) + Sub-Plan 2 (live Playwright, needs user) | Full Phase 5 adapter needs authenticated Chrome profile + CAPTCHA handling; cannot run unattended without risking account bans. Sub-Plan 1 lands the plumbing (Mode=web, adapter stub, UI column disabled) so Sub-Plan 2 is a drop-in replacement of the NotImplementedError raises. |
| 2026-04-24 | `WebModeNotImplemented` sentinel + `RuntimeError` re-raise in `run_generate` web branch | Swallowing bare `NotImplementedError` would also hide real bugs in later Sub-Plan 2 code. Sentinel subclass + re-raise-as-RuntimeError-with-user-message is the only pattern the runner catches; anything else propagates normally. |
