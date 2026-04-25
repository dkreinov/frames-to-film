# Phase 7 — Sub-Plan 2: Eval harness + reference test set

**Status:** pending
**Size:** 1-2 days
**Depends on:** 7.1 (judges callable + envelope shape locked)
**Unblocks:** 7.3 (calibration), and the eval gate of every later sub-plan

## Goal

Stand up a reference-driven eval harness that walks 5 fixed projects through the full pipeline, captures per-rubric scores + cost + time, and appends a row to `eval_runs.csv`. Produce a baseline run (current pipeline + 7.1 judges only, no story changes yet) so future sub-plans have a comparison anchor.

## Inputs / outputs

**Inputs**
- 5 photo-set projects to seed `fixtures/eval_set/` (decision below)
- Working judges from 7.1
- Real API keys (FAL + Gemini at minimum)

**Outputs**
- `fixtures/eval_set/{project_n}/photos/*.jpg` — fixed reference inputs
- `fixtures/eval_set/{project_n}/expected_brief.json` — brief that matches the photos
- `tools/eval_runner.py` — script that runs all 5 through the pipeline
- `eval_runs.csv` — append-only row per run (committed; treat like a journal)
- `docs/roadmap/eval_baseline_2026-04.md` — the first row's interpretation, written by hand

## Step list

### 1. Pick the 5 reference projects
Two options:
- **A:** Use 5 projects from the user's existing photo library (most realistic)
- **B:** Use 5 synthetic / fixture-style sets we control (cats wet-test + 4 new)

Default: **A** for 3 of the 5, **B** for 2 (cats + 1 contrived edge case). Diversity targets: life-montage subject, 3-act, travel, event, day-in-life.

### 2. Build the fixture skeleton
- `fixtures/eval_set/01_life_montage/` — 6 photos (Olga-style), `expected_brief.json` with arc=life-montage
- `fixtures/eval_set/02_3act_cats/` — copy from wet test
- `fixtures/eval_set/03_travel_diary/` — 6 photos
- `fixtures/eval_set/04_event_recap/` — 6 photos
- `fixtures/eval_set/05_day_in_life/` — 6 photos
- Each `expected_brief.json` is a stub today; gets enriched after 7.4 ships brief input

### 3. `tools/eval_runner.py`
- Walks each project through the pipeline programmatically (no UI)
- Calls the same backend services the UI calls (no special path)
- Captures per-stage timings + costs
- Writes one row to `eval_runs.csv` per project + one summary row per full run
- CLI: `python tools/eval_runner.py --label "post-7.1-baseline"`

### 4. `eval_runs.csv` schema
```csv
run_label,project_id,timestamp,arc_type,
prompt_align_mean,prompt_align_min,
clip_visual_mean,clip_anatomy_defect_pct,
movie_story,movie_continuity,movie_visual,movie_arc,
weakest_seam,reroll_count,
cost_usd,wall_time_s,model_versions
```

Append-only. Never mutate prior rows. Git-tracked.

### 5. Run the baseline
- Set `JUDGES_ENABLED=on`
- `python tools/eval_runner.py --label "post-7.1-baseline"`
- All 5 projects run; CSV row appended for each
- Total cost: ~$2.50 (5 × $0.50)

### 6. Write `eval_baseline_2026-04.md`
A short hand-written interpretation of the baseline:
- Median scores per dimension
- Standout failures (which projects scored worst on which dim)
- Anything that surprised the operator
- Sets the "score to beat" for sub-plan 7.4

### 7. Tests
- Smoke: `tools/eval_runner.py` with mock-mode set runs without crashing on 1 fixture
- No CI run of the full eval (too expensive); manual cadence per `phase_7_plan.md`

## Validation gates

1. **Logical:** Smoke test green; one full eval run completes without exception.
2. **General design:** advisor pass — confirm CSV schema is extensible (e.g. when 7.4 adds story scores) without breaking earlier rows.
3. **Working:** `eval_runs.csv` has 5 baseline rows + 1 summary row; `eval_baseline_2026-04.md` committed.

## Open questions

| Q | Default proposal | Decide when |
|---|---|---|
| Test-set composition (real photos vs synthetic) | 3 real + 2 synthetic | Step 1 (user picks photos) |
| CSV vs SQLite for run history | CSV (git-friendly, human-readable) | Locked here |
| Frequency of full eval runs | Every sub-plan close + on-demand | `phase_7_plan.md` decision #3 |
| Where to store generated mp4s from eval runs | `fixtures/eval_set/{n}/runs/{run_label}/` (gitignored) | Step 3 |

## Rollback / failure mode

If runner crashes on a specific project: skip + log + continue (eval is a journal, partial rows OK).
If a project produces wildly outlier scores (e.g. all 1s or all 5s): quarantine that project from the test set; investigate model or judge behaviour.

## Memory pointers

- `phase_7_flow.md` — `JudgeScore` envelope (this sub-plan reads it)
- `project_quality_vision.md` — eval rubric dimensions
- `project_business_model.md` — cost ceiling per movie ($0.50 typical)
