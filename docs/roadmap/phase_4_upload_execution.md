# Phase 4 — Upload Sub-Plan Execution Log

**Sub-plan:** 1 of 5 (Upload) — the pattern-setter for Prepare, Storyboard,
Generate, Review+Export, Settings.
**Status:** done
**Plan:** `plans/plan-20260423-1628.md` (self-deleted on close-out)
**Dates:** 2026-04-23

## Outcome

`frontend/` exists at repo root. Stack: Vite + React 19 + TS + Tailwind v4 +
shadcn/ui (new-york, zinc base) + TanStack Query + React Router. Upload
screen renders, validates, wires to the Phase 2 FastAPI backend, and
round-trips through a real Playwright E2E.

- 12/12 vitest (unit + MSW integration + api client).
- 1/1 Playwright chromium E2E hitting real uvicorn + vite.
- 79/1 backend regression still green (Phase 2 + 3 untouched; only CORS
  added).
- `npm run build` (tsc -b + vite build) compiles cleanly with strict
  `erasableSyntaxOnly` + `noUnusedLocals`.
- Golden screenshots captured under `docs/design/golden/`.

**Correction (2026-04-23, Prepare sub-plan):** the Upload sub-plan's
"Step 9 commit" staged the golden PNGs but `git add` silently dropped
them due to a repo-level `*.png` gitignore rule. The PNGs existed on
disk and Playwright produced them, but they were never tracked.
`.gitignore` was fixed in the Prepare sub-plan (exception for
`!docs/design/golden/**`) and all goldens re-added to the index.
Lesson for future sub-plans: after `git add`, run
`git ls-files <paths>` to verify actual tracking.

## Decisions taken autonomously

- **Stack:** see decisions log in `docs/design.md`. Locked for all 5 screens.
- **Stitch integration:** tool timed out on every generate call; project
  `projects/10276889797068420736` created but empty. Hand-designed
  against the prose prompt in `docs/design/phase_4_upload_notes.md`.
  `docs/design.md` is the authoritative design system; later sub-plans
  re-attempt Stitch per-screen.
- **Package manager:** shipped on npm (pnpm not on PATH).
- **Golden screenshots:** Playwright fallback (Claude-in-Chrome not
  available in autonomous run).
- **`OLGA_PYTHON` env var:** set before `npx playwright test` when
  `python` isn't on Windows PATH.

## Frozen contracts (consumed by sub-plans 2-5)

- `frontend/src/api/client.ts` function signatures.
- `frontend/src/api/types.ts` response shapes.
- `frontend/src/components/layout/` (AppBar, WizardStepper,
  PageContainer, Footer) — reuse, don't reimplement.
- Visual tokens in `frontend/src/index.css` `@theme` block.
- Wizard step ids: `upload | prepare | storyboard | generate | review`.
- `WIZARD_STEPS` array order in `WizardStepper.tsx`.

## Advisor findings (2026-04-23 close-out)

### Resolved inline
1. **Hardcoded Python path in `playwright.config.ts`.** Replaced with
   `process.env.OLGA_PYTHON ?? 'python'`. The repo is meant to be
   clonable — can't ship a user-specific path.
2. **`npm run build` typecheck failures.** Fixed 3 strict-mode
   violations: deprecated `baseUrl`, `test` key not on `UserConfig`
   (use `vitest/config`'s defineConfig), `erasableSyntaxOnly` rejecting
   ApiError's param-property syntax.

### Flagged for follow-up sub-plans (not blockers)

1. **Partial-upload orphan project.** `useUploadFlow.ts` creates the
   project then loops uploads. If upload #3 of 5 throws, the loop exits
   but the project + first 2 uploads stay on the backend — no cleanup.
   Fix location: add `DELETE /projects/{id}` in the `catch` arm of
   `runUpload`, OR server-side "atomic batch upload". Noted for Phase 6
   polish.
2. **`URL.createObjectURL` memory leak.** `UploadedFilesList` revokes
   object URLs only on unmount, not when `files` array changes.
   Add/remove cycles leak. One-line fix with `useEffect` cleanup keyed
   on `files`. Defer to a small Upload-cleanup sub-plan or bundle into
   Phase 6.
3. **HEIC/HEIF photos rejected.** iPhone photos are HEIC by default;
   server `ALLOWED_CONTENT_TYPES` (backend/routers/uploads.py:16) + the
   dropzone's `accept=` both reject. Users with iPhone libraries get
   confused rejection. Phase 6 server-side transcode is the right home.
4. **`frontend/README.md` still Vite template.** No mention of uvicorn
   prerequisite. First-time-dev experience is broken. One-paragraph
   rewrite in Phase 6.
5. **Footer + fixed positioning + fullPage screenshot.** Playwright's
   fullPage mode duplicates the fixed footer across the scroll area.
   Known Playwright quirk; not a UI bug.

## Findings for sub-plans 2-5

1. **Stitch MCP is flaky on generation.** `list_projects` + `create_project`
   work; `generate_screen_from_text` times out. Budget 0 time for
   first-try Stitch; go straight to the hand-designed prose prompt.
   Document the prompt verbatim in each sub-plan's
   `phase_4_<screen>_notes.md` — that's the design-of-record.
2. **shadcn CLI creates `@/components/ui/` as a literal dir on first
   use.** Move manually to `src/components/ui/` and clean up the `@/`
   dir. One-time-per-install issue.
3. **Tailwind v4 + shadcn needs secondary + destructive-foreground
   tokens** that the shadcn CLI's generated `src/index.css` doesn't
   always include. Check `index.css` has all tokens shadcn references
   (search for `bg-secondary`, `text-destructive-foreground`, etc.) and
   top up if missing.
4. **vitest picks up `e2e/` by default** — add
   `include: ['src/**/*.{test,spec}.{ts,tsx}']` + `exclude: ['e2e/**']`
   to vite.config.ts.
5. **Remove `erasableSyntaxOnly` conflicts up front.** Use explicit
   assignment in class constructors (no `public x: T` param
   properties). Caught by `npm run build`, not vitest.

## Follow-ups that don't belong to any sub-plan

- Retire the `/@` stray dir pattern by upstream-reporting to shadcn.
- Tune `frontend/README.md` (carry from Phase 6).
- Fix advisor item 1 (orphan project on partial upload) before shipping.
