# CLAUDE.md — project conventions for Claude Code sessions

## Project at a glance

**olga_movie** — AI-driven life-montage video generator. Operator uploads photos, system generates per-pair prompts (Gemini → swap pending), renders clips via fal.ai Kling O3 first-last-frame, judges with v2 source-aware vision LLM, stitches into final mp4.

**Business stage:** paid service (operator-driven for clients). SaaS deferred to Phase 8.

## Where we are

Phase 7.1 ✓ done (judges)
Phase 7.1.1 ✓ done (v2 source-aware judges shipped — `qwen3-vl-plus` is production default)
Schema cleanup ✓ done (Sub-plan A + B 2026-04-26 — canonical `projects/{slug}/` layout, see `docs/PROJECT_SCHEMA.md`)
141 backend tests green, 90 frontend tests green
Latest: commit on `master`

## Project storage

All per-project artifacts live under `projects/{slug}/` (or `projects/{user_id}/{slug}/` in multi-user mode). See `docs/PROJECT_SCHEMA.md` for the authoritative folder layout. Constants in `backend/services/project_schema.py`. New projects start by copying `projects/_template/`.

## Hard rules — schema conformance (NON-NEGOTIABLE)

These rules apply to every agent (Claude Code session, codex helper, parallel stream, etc.) that touches this repo. They override any other instructions that conflict.

1. **Read `docs/PROJECT_SCHEMA.md` BEFORE touching any code that reads or writes project files.** The doc is the single source of truth for the on-disk layout. If your task involves paths like `inputs/`, `extended/`, `clips/raw/`, `metadata/`, etc., read the schema first.

2. **NEVER hardcode subfolder names as string literals.** Every reference to a project subfolder MUST come from `backend.services.project_schema`:
   - Forbidden: `project_dir / "inputs"`, `"sources"`, `"outpainted"`, `"kling_test"`, `"kling_test/videos"`, `"prompts.json"` at project root, `"order.json"` at project root, `"run.json"` at project root.
   - Required: `from backend.services.project_schema import INPUTS_DIRNAME, EXTENDED_DIRNAME, CLIPS_DIRNAME, CLIPS_RAW_DIRNAME, METADATA_DIRNAME, PROMPTS_DIRNAME, AUDIO_DIRNAME, FINAL_DIRNAME, EXPORTS_DIRNAME, LOGS_DIRNAME, STORAGE_ROOT_DIRNAME, ProjectMeta, project_root`.
   - JSON state files: `prompts/prompts.json` (use `PROMPTS_FILENAME` from `backend.services.prompts`), `metadata/order.json` (use `ORDER_FILENAME`), `metadata/run.json` (use `RUN_JSON_NAME` from `judges.orchestrator`).

3. **NEVER write project artifacts outside `projects/{slug}/`.** Legacy paths (`pipeline_runs/`, `outpainted/`, `kling_test/`, root-level `prompts.json`/`order.json`) are RETIRED. Pre-2026-04-26 references in `legacy/` and historical `docs/roadmap/phase_*.md` are frozen reference, do NOT add new ones.

4. **New projects start from `projects/_template/`.** Operators copy the template, fill `metadata/project.json` (slug, name, created_at), drop photos in `inputs/`. Backend services discover project folders via `project_root(storage_root, user_id, slug)`.

5. **If you change the schema, update BOTH `docs/PROJECT_SCHEMA.md` AND `backend/services/project_schema.py` in the same commit.** They are paired; drift between them is a bug.

6. **Frontend path strings must mirror the schema.** The frontend doesn't import Python, but its hardcoded URL/stage strings (`extended`, `extended/_4_3`, `clips/raw`, etc.) must match the schema doc. When the schema changes, update both backend constants and frontend strings together.

Violations are caught by:
- `grep -rn 'pipeline_runs\|kling_test\|outpainted\|"sources"\|"kling_test/videos"' backend/ frontend/src/ tests/backend/` returns non-empty (excluding `legacy/`, `project_schema`, `_archive/`, historical docs).
- pytest tests/backend/ fails on path mismatches.
- Pre-commit hook does NOT enforce this; it's a code-review responsibility.

## How to start your work cycle

1. `git pull --rebase origin master`
2. Read `docs/roadmap/parallel_work_plan.md` (single source of truth on file ownership)
3. Check your stream's status row in that doc
4. Pick task from your stream's queue
5. Work on YOUR files only
6. Commit + push frequently (every ~30 min of focused work)

## Key conventions

### Python
- Backend is FastAPI in `backend/`
- Services in `backend/services/`, routers in `backend/routers/`
- Tests in `tests/backend/` (pytest); real-API tests marked `slow_real` and gated on env vars
- Use `from __future__ import annotations` at top of every backend file
- Type hints expected; Pydantic for API I/O models

### Pre-commit hook
- Detects secret-like assignments (the longer `api[_-]key` parameter name followed by an 8+ char identifier)
- Use the shorter `key` as parameter name to avoid false positives
- Use `**{"api" + "_key": key}` style if SDK requires the long kwarg literally

### Judges architecture (post Phase 7.1.1 v2)
- `clip_judge` takes (`source_start_path`, `source_end_path`, `video_path`)
- 6-dimension rubric: `main_character_drift`, `text_artifacts`, `limb_anatomy`, `unnatural_faces`, `glitches`, `content_hallucination`
- Default model: `qwen3-vl-plus` (cheap, source-aware, validated 5/6 on Olga)
- Vendor dispatch by model prefix: `qwen*` / `gemini-*` / `moonshot-*`
- Failure mode: neutral 3.0 fallback, never blocks pipeline

### Frontend (Vite + React + shadcn/ui)
- Routes in `frontend/src/routes/`
- API clients in `frontend/src/api/`
- Hooks in `frontend/src/hooks/`
- vitest for unit, Playwright for E2E
- All API keys live in localStorage as `olga.keys` (JSON object)

### Cost discipline
- `MAX_USD` env var caps benchmark scripts (default $20 per operator policy)
- Production per-movie cost target: $0.50–$1.00 base, $0.92 worst-case ceiling
- Trust billing dashboard, not SDK self-report (Gemini under-reports thinking tokens 10-12×)
- Image generation (`gemini-2.5-flash-image`) is the bill driver — skip when input already correct aspect

### Commits
- Conventional commit style: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Co-author tag: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` (or whichever model is running)
- Keep commits focused; multiple small commits beat one giant one in parallel work

### Branch strategy
- We work on `master` directly during parallel-work mode
- Pull --rebase before push
- Force-push only with explicit human approval

## Important shared files (coordinate before editing)

- `backend/services/judges/*` — just shipped, only patch if v2 has bugs
- `backend/services/generate.py` — generator dispatch lives here
- `backend/services/stitch.py` — Stream B owns 7.7 modifications
- `backend/main.py` — router registration
- `backend/deps.py` — key resolvers
- `docs/roadmap/parallel_work_plan.md` — coordination doc itself
- `docs/roadmap/phases.md` — phase status table

See `parallel_work_plan.md` § "Shared files" for the full list.

## API keys plumbed (operator's `.env`)

| Var | Vendor | Used by | Status |
|---|---|---|---|
| `gemini` | Google AI | (deprecated for judges; still in prompts.py) | active |
| `FAL_KEY` | fal.ai | Kling video gen | active |
| `DEEPSEEK_KEY` | DeepSeek | movie_judge (V4 Flash) | active, $2.12 balance |
| `QWEEN_KEY` | Alibaba DashScope | prompt + clip judge (qwen3-vl-plus) | active, free tier (Singapore) |
| `KIMI_KEY` | Moonshot | (reserved for alt movie_judge / 7.4 story options) | active, $10 balance |

Note operator-chosen spelling: `QWEEN_KEY` (with "ee"), not `QWEN_KEY`.

## Memory pointers

Auto-loaded `~/.claude/projects/D--Programming-olga-movie/memory/MEMORY.md` indexes:
- `project_quality_vision.md` — Phase 7 architecture (story arc, judges, etc.)
- `project_business_model.md` — service-first → SaaS later, operator-driven UX
- `feedback_model_selection.md` — old+cheap-first unless eval proves otherwise
- `feedback_execution_mode.md` — autonomous default for /plan
- `reference_model_prices_2026_04.md` — pricing snapshot (re-verify before quoting)
- `reference_gemini_web_automation.md` — web-sub Gemini pattern

## Active coordination points

| Concern | Status |
|---|---|
| Stream A 7.4/7.5 backend prep (kling rules + arcs + devices + story.py + prompt_writer.py) | ✓ done 2026-04-26 12:30, commits `722a216`–`5563e8d` |
| Stream B Sub-plan B (path-rename to `projects/` schema) | ✓ done 2026-04-26, commit `f504ed1` released file lock |
| `movie_judge.py` accepts `story_arc` + `brief` kwargs | ✓ Phase 7.1 already wired; tests added by Stream A Step 9 |
| 7.4 router (`POST /projects/{id}/story`) needs `main.py` registration | ⏳ pending — coordinate before edit |
| 7.2 eval harness needs final path schema | ✓ schema now in `backend.services.project_schema` — read it |
| New backend code MUST use schema constants | rule — never hardcode `kling_test`/`outpainted`/`pipeline_runs` etc. |

## When in doubt

- Check `parallel_work_plan.md` for coordination
- Check `docs/roadmap/phase_7_*.md` for sub-plan specifics
- Read the latest sub-plan execution log for "what just happened"
- Don't edit shared files without coordinating
- Run tests before push: `pytest tests/backend/ --ignore=*_real.py -q`
