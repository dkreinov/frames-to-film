# Phase 2 — Execution Log

**Phase:** FastAPI engine + mock mode + project isolation
**Status:** done
**Plan:** `plans/plan-20260423-1433.md` (self-deleted on close-out)
**Dates:** 2026-04-23

## Outcome

FastAPI service under `backend/` with 14 endpoints covering project CRUD,
uploads, four stage jobs (prepare/extend/generate/stitch), review, job
polling, and artifact download. SQLite row index at
`pipeline_runs/index.db` + per-project filesystem tree at
`pipeline_runs/<user>/<project>/`. `GENERATION_MODE=api|mock` honored per
stage; mock serves the existing `tests/fixtures/fake_project/` 6-frame
Pixar-Cosmo fixture without spending API cost. Streamlit `review_app.py`
runs untouched alongside — FastAPI is additive.

## Test coverage

- `tests/backend/` — 45 unit contract tests (health, db, projects, uploads,
  jobs, prepare, extend, generate, review, stitch, artifacts). Each router
  has its own file; isolation via `app.dependency_overrides` for db_path,
  storage_root, and fixture_root.
- `tests/integration/test_e2e_mock.py` — 1 test drives the full pipeline
  via `TestClient` → 6 uploads → prepare/extend/generate/stitch jobs all
  transition to `done` → mp4 downloaded and validated.
- Full suite: 46 passed + 1 skipped (ffprobe unbundled).
- Pre-existing `tests/test_review_app_ui.py` failures (2) unchanged —
  caused by the earlier Streamlit refactor, not Phase 2.

## Frozen contracts

- Endpoints read optional `X-User-ID` header; default `"local"`.
- Job row schema (`jobs` table): `job_id, project_id, user_id, kind, status, payload (JSON), error, created_at, updated_at`.
- Every refactored script (`outpaint_images.py`, `outpaint_16_9.py`, `generate_all_videos.py`, `concat_videos.py`) exposes a `run(...)` entry point. CLI `main()` unchanged; Phase 1 `clean_if_enabled` hooks all verified present post-refactor.
- `backend/services/<stage>.py` contract: `run_<stage>(project_dir: Path, mode: str) -> dict` and `<stage>_runner(**payload) -> dict`.

## Findings for Phase 3

### Phase 2 blockers — resolved 2026-04-23 (post-phase hotfix)

The two api-mode blockers called out below were fixed out-of-phase
(separate hotfix commit) after Phase 2 close-out, because leaving them
to rot until Phase 3 would have made api-mode untestable in any
integration environment. See `tests/backend/test_script_errors.py` and
`tests/backend/test_script_threadsafe.py` for the pins.

1. **~~`sys.exit(1)` will crash the uvicorn worker~~ → raises RuntimeError.**
   Three sites found (advisor flagged one; grep caught two more):
   - `outpaint_images.get_client` — `sys.exit(1)` → `raise RuntimeError`
   - `generate_all_videos.get_jwt` — `sys.exit(...)` → `raise RuntimeError`
   - `concat_videos.main` — `sys.exit(1)` (on ffmpeg missing) → `raise RuntimeError`
   - `outpaint_16_9.get_client` — already raised RuntimeError, no change needed.
   Pinned by 4 tests asserting each raises `RuntimeError` (not SystemExit)
   on the failure path.

2. **~~Module-global swap in `run()` is not thread-safe~~ → serialised by `_RUN_LOCK`.**
   Each of `outpaint_images.py`, `outpaint_16_9.py`,
   `generate_all_videos.py`, `concat_videos.py` now defines a module-level
   `_RUN_LOCK = threading.Lock()` and wraps its `run()` body in
   `with _RUN_LOCK:`. A parametrized test patches each module's
   `main()` to block on an `Event`, spawns two threads calling `run()`,
   and asserts the second thread waits for the first to release before
   entering — confirming serialisation under real concurrency.

### Non-blockers

3. **Path-traversal test asserts `status_code in (403, 404)`.** FastAPI's
   path parser normalizes some traversals before the handler runs, which
   means a broken `_resolve_safe` could let the test pass via a 404 path.
   Phase 3 or Phase 6 can add a direct unit test on `_resolve_safe`.

4. **`ffprobe.exe` not bundled** alongside `ffmpeg.exe` in `tools/` — the
   Phase 2 `test_stitch_duration_equals_sum_of_segments` test skips. If
   exact-duration validation is wanted later, bundle ffprobe.

5. **Pre-existing `test_review_app_ui.py` failures** remain red. Orthogonal
   to Phase 2; fix alongside Phase 4's React rewrite or sooner if Streamlit
   regression protection matters.

## Design decisions taken

- **SQLite for rows, filesystem for blobs.** SQLite is stdlib; TEXT IDs +
  JSON payload columns let later phases extend without migration.
- **Single-user-now, schema-ready (answer C to the auth question).**
  `user_id` column on every row; default `"local"`; no auth enforced.
  Phase 4 can add bearer tokens as a config flag, not a schema change.
- **BackgroundTasks + polling** over Celery/Redis. In-process, no extra
  infra. Adequate for single-user local tool; trivial to swap later.
- **`TestClient` for E2E**, not a live uvicorn subprocess. Eliminates
  port-flake and BackgroundTasks-timing races.
- **Scope pushback on Step 13** (originally: pre-bake all downstream
  artifacts into the fixture). Reduced to a README note; the mock
  services regenerate everything at test runtime from the 6 source
  frames.

## Follow-ups (non-blocking)

- Bundle `ffprobe.exe` in `tools/` if future tests need exact duration.
- Add a direct `_resolve_safe` unit test.
- Tune pre-commit hook regex (still a carryover from Phase 1).
