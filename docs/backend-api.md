# Backend API (Phase 2)

FastAPI service under `backend/`. Boot:

```
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## Conventions

- All endpoints accept optional `X-User-ID` header; defaults to `"local"`. Rows and on-disk artifacts are scoped per user.
- Disk layout: `pipeline_runs/<user_id>/<project_id>/{sources,outpainted,kling_test,kling_test/videos,kling_test/videos/full_movie.mp4}`.
- Row index: `pipeline_runs/index.db` (SQLite) — tables `projects`, `uploads`, `jobs`, `segments`.
- Long-running stages return `202 {job_id}` and execute via `BackgroundTasks`. Poll `GET /projects/{id}/jobs/{job_id}` for status (`pending|running|done|error`).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| POST | `/projects` | Create project |
| GET | `/projects` | List projects (user-scoped) |
| GET | `/projects/{id}` | Project details |
| DELETE | `/projects/{id}` | Delete project + disk dir |
| POST | `/projects/{id}/uploads` | Upload source image (multipart) |
| GET | `/projects/{id}/uploads` | List uploads |
| DELETE | `/projects/{id}/uploads/{filename}` | Remove an upload |
| POST | `/projects/{id}/prepare` | Stage 1: 4:3 normalize (mode: mock\|api) |
| POST | `/projects/{id}/extend` | Stage 2: 4:3 → 16:9 (mode: mock\|api) |
| POST | `/projects/{id}/generate` | Stage 3: video pair synthesis (mode: mock\|api) |
| POST | `/projects/{id}/segments/{seg_id}/review` | Mark verdict winner\|redo\|bad |
| POST | `/projects/{id}/stitch` | Stage 4: concat → full_movie.mp4 |
| GET | `/projects/{id}/jobs/{job_id}` | Poll job status |
| GET | `/projects/{id}/artifacts/{stage}/{name}` | Stream any artifact file |
| GET | `/projects/{id}/download` | Shortcut for full_movie.mp4 |

## Modes

Stage endpoints accept `{"mode": "mock"|"api"}`.

- **mock** — copies `tests/fixtures/fake_project/frame_*_gemini.png` → outpainted/*.jpg, then progressively builds downstream artifacts (ffmpeg stubs for videos). Zero API cost, deterministic, offline. Used by tests and the CI E2E smoke.
- **api** — delegates to the existing pipeline scripts (`outpaint_images.run`, `outpaint_16_9.run`, `generate_all_videos.run`, `concat_videos.run`). Requires `gemini` key for image stages and `KLING_*_ACCESS_KEY` / `KLING_*_SECRET_KEY` for the generate stage. See caveats in `docs/roadmap/phase_2_execution.md`.

## Contracts

**Jobs row** (also returned by `GET /projects/{id}/jobs/{job_id}`):

```
{
  "job_id": "<uuid4-hex>",
  "project_id": "<uuid4-hex>",
  "user_id": "local",
  "kind": "prepare|extend|generate|stitch",
  "status": "pending|running|done|error",
  "payload": {"mode": "mock", "project_dir": "...", ...},
  "error": null,
  "created_at": "<iso8601>",
  "updated_at": "<iso8601>"
}
```

**Segments row** (one per `seg_id` per project):

```
{
  "project_id": "...",
  "seg_id": "seg_1_to_2",
  "verdict": "winner|redo|bad",
  "notes": null,
  "updated_at": "<iso8601>"
}
```

Repeated POSTs to `/segments/{seg_id}/review` UPSERT the verdict.

## Tests

- Unit contract tests under `tests/backend/` (46 cases). Each router has its own file; DB + storage dirs injected via `app.dependency_overrides`.
- Integration smoke at `tests/integration/test_e2e_mock.py` — full pipeline via `TestClient`.
- Run: `"C:/Users/nishtiak/AppData/Local/Programs/Python/Python312/python.exe" -m pytest tests/backend tests/integration -v`.

`TestClient` runs `BackgroundTasks` synchronously, so tests read the final job row without polling.
