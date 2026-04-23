# olga_movie Frontend Architecture

**Scope:** `frontend/` — React app that drives the Phase 2 FastAPI backend.
Non-authoritative on visual design (see `docs/design.md` for that).

## Stack

- **Build:** Vite 8 (`vite.config.ts` — `test` key comes from
  `vitest/config`, not raw `vite`).
- **UI:** React 19 + TypeScript 6 (strict, `erasableSyntaxOnly: true`).
- **Routing:** `react-router-dom` via `createBrowserRouter`.
- **Data layer:** `@tanstack/react-query` for server state; `useState`
  for local.
- **Styling:** Tailwind v4 via `@tailwindcss/vite`; theme tokens in
  `src/index.css` `@theme` block (OKLCH, light + dark).
- **Component primitives:** shadcn/ui (new-york style, zinc base),
  installed to `src/components/ui/`.
- **Icons:** `lucide-react`.
- **Tests:** Vitest (unit + MSW integration), Playwright
  (chromium-headless-shell for E2E).

## File layout

```
frontend/
├── components.json              shadcn config (new-york, zinc, cssVariables)
├── package.json                 scripts: dev, build, test, playwright
├── playwright.config.ts         webServer boots uvicorn + vite
├── vite.config.ts               plugins, path alias, vitest config
├── tsconfig.app.json            strict, paths: @/* -> src/*
├── e2e/                         Playwright specs (not vitest)
├── public/                      static assets
└── src/
    ├── App.tsx                  RouterProvider only
    ├── main.tsx                 QueryClientProvider + render
    ├── index.css                Tailwind v4 + @theme tokens
    ├── api/
    │   ├── types.ts             mirrors FastAPI response schemas
    │   ├── client.ts            fetch-based; exports functions, not hooks
    │   └── client.test.ts       MSW-mocked contract tests
    ├── components/
    │   ├── ui/                  shadcn primitives (button, card, ...)
    │   ├── layout/              AppBar, WizardStepper, PageContainer, Footer
    │   ├── upload/              DropzoneCard, UploadedFilesList
    │   └── BackendStatus.tsx    dev-only backend-reachability banner
    ├── lib/
    │   └── utils.ts             cn() helper
    ├── routes/
    │   ├── router.tsx           route tree
    │   ├── UploadScreen.tsx     Step 1 wizard
    │   ├── UploadScreen.test.tsx
    │   ├── UploadScreen.integration.test.tsx
    │   └── useUploadFlow.ts     createProject + uploadFile + navigate
    └── test/
        └── setup.ts             jest-dom matchers
```

## Running locally

```bash
# Terminal 1 — backend
uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — frontend
cd frontend
npm install           # first time only
npm run dev           # http://127.0.0.1:5173

# Tests
cd frontend
npm run test          # vitest (unit + MSW integration)
npx playwright test   # E2E; set OLGA_PYTHON if python isn't on PATH
```

## CORS

`backend/main.py` allows `http://127.0.0.1:5173` + `http://localhost:5173`
via `CORSMiddleware`. Proved by `tests/backend/test_cors.py`.

## API client contract

- Single module `src/api/client.ts` exports function-per-endpoint:
  `getHealth`, `createProject`, `uploadFile`, `listUploads`, `getJob`.
- Each uses `fetch()` + `parse<T>()` which throws `ApiError(status, msg)`
  on non-2xx.
- Response shapes live in `src/api/types.ts` and mirror FastAPI's
  Pydantic models exactly. Keep in sync when backend schemas change.
- `API_BASE` defaults to `http://127.0.0.1:8000` and can be overridden
  via `VITE_API_BASE` env.

## Wizard routing convention

```
/                               -> redirect to /projects/new/upload
/projects/new/upload            -> UploadScreen (pre-creation)
/projects/:id/upload            -> UploadScreen (post-creation, edit)
/projects/:id/prepare           -> Prepare (future sub-plan)
/projects/:id/storyboard        -> Storyboard (future sub-plan)
/projects/:id/generate          -> Generate (future sub-plan)
/projects/:id/review            -> Review+Export (future sub-plan)
/settings                       -> Settings (future sub-plan)
```

All wizard screens render `<AppBar currentStep="..." />` on top and
`<Footer />` on bottom (fixed). Main content in `<PageContainer />` with
`max-w-[960px]`.

## Testing strategy

- **Vitest unit:** per-component render + interaction tests. Mock API
  hooks via `vi.mock` to isolate network. `src/**/*.test.tsx`.
- **Vitest integration:** per-screen MSW-backed tests hitting the real
  `useUploadFlow` / client code paths. `src/**/*.integration.test.tsx`.
- **Playwright E2E:** real browser against real uvicorn + vite. `e2e/`
  excluded from vitest. One happy-path per screen + one golden
  screenshot spec per screen.
- **Backend regression:** `pytest tests/backend tests/integration` must
  stay green after every frontend change that touches `backend/` (e.g.
  CORS changes in Phase 4).

## Known limitations

- First-run `npx shadcn add ...` creates a literal `@/` dir; manual move
  to `src/components/ui/` required (see phase_4_upload_execution.md
  finding #2).
- Stitch MCP `generate_screen_from_text` times out consistently as of
  2026-04-23; each sub-plan's design falls back to the prose prompt
  captured verbatim in `docs/design/phase_4_<screen>_notes.md`.
