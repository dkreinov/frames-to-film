# Eval baseline — 2026-04-26 (Phase 7.2)

**Run label:** `post-7.4-baseline-mock`
**Mode:** mock (zero LLM, zero Kling spend)
**Fixtures:** 01_cats (3-act-heroic), 02_olga_slice (life-montage)
**Cost:** $0.00
**Wall time:** ~7s total

This is the inaugural row of `fixtures/eval_set/eval_runs.csv`. Mock-mode scores are deliberately neutral (3.0 across the board) because no real LLM calls fired. Subsequent api-mode runs will produce real scores; the delta from this baseline is what tells us whether Phase 7.4/7.5 changes actually lifted quality.

## How to read the CSV

`fixtures/eval_set/eval_runs.csv` is append-only. Each row = one fixture run. Columns:

| Column | Meaning |
|---|---|
| `run_label` | Operator-supplied tag for the run (e.g. "post-7.4-baseline-mock", "post-rubric-tweak", "real-A1") |
| `fixture_id` | Folder name under `fixtures/eval_set/` (e.g. `01_cats`, `02_olga_slice`) |
| `timestamp` | UTC ISO 8601 of when the row was written |
| `arc_type` | From `metadata/expected_brief.json` — drives which story arc YAML loads |
| `n_pairs` | N source frames - 1 (life_montage with 6 frames = 5 pairs) |
| `mode` | `mock` or `api` |
| `prompt_align_mean` / `prompt_align_min` | prompt_judge across all pairs — mean + min |
| `clip_*_mean` (×6) | clip_judge per-rubric means: main_drift, text_artifacts, limb_anatomy, unnatural_faces, glitches, content_hallucination |
| `movie_story_coh` / `movie_continuity` / `movie_visual` / `movie_arc` | movie_judge 4 dimensions (1-5 each) |
| `weakest_seam` | movie_judge's call on which pair index has the worst transition (1-indexed) |
| `cost_usd` | Real billed cost for this fixture's run (sum of all judge calls) |
| `wall_time_s` | Wall-clock time end-to-end |
| `model_versions` | Snapshot of which models the judges defaulted to |

Empty cells = mock mode (no LLM calls fired) OR judge skipped due to missing data.

## Rubric thresholds (proposed — tune as we collect more data)

These are the scores a clip needs to reach to be **client-shippable** for a paid life-montage delivery. Used by judge gates + re-roll budgets.

| Dimension | Ship threshold | Re-roll threshold | Notes |
|---|---|---|---|
| `prompt_align_mean` | ≥ 4.0 | < 3.0 | If model misunderstood the prompt, render is wasted |
| `clip_main_drift_mean` | ≥ 4.0 | < 3.0 | Main character (Olga) must look like Olga |
| `clip_text_artifacts_mean` | ≥ 4.0 | < 3.0 | Hebrew/English text must not garble (per Phase 7.1.1 finding) |
| `clip_limb_anatomy_mean` | ≥ 4.0 | < 3.0 | Missing arms / extra fingers blocks ship |
| `clip_unnatural_faces_mean` | ≥ 3.5 | < 2.5 | Some uncanny is unavoidable; severe is not |
| `clip_glitches_mean` | ≥ 3.5 | < 2.5 | Heavy ghosting / blur is reroll territory |
| `clip_content_halluc_mean` | ≥ 4.0 | < 3.0 | Kling fabricating scenes not in either source = real failure (caught the geometry-teacher classroom fabrication in Phase 7.1.1) |
| `movie_story_coh` | ≥ 3.5 | < 2.5 | Movie tells a coherent story |
| `movie_continuity` | ≥ 4.0 | < 3.0 | Main character preserved across cuts |
| `movie_visual` | ≥ 3.5 | < 2.5 | Aggregate visual quality |
| `movie_arc` | ≥ 3.0 | < 2.5 | Emotional arc lands |

**Re-roll budget:** 1 retry per movie (worst case +$0.42 Kling). If clip fails ship threshold AND re-roll budget exhausted, operator escalates to manual review.

## Baseline values (2026-04-26 mock run)

| Fixture | n_pairs | movie_story_coh | movie_continuity | movie_visual | movie_arc | weakest_seam | cost_usd |
|---|---|---|---|---|---|---|---|
| 01_cats | 5 | 3.0 | 3.0 | 3.0 | 3.0 | (none) | $0.00 |
| 02_olga_slice | 5 | 3.0 | 3.0 | 3.0 | 3.0 | (none) | $0.00 |

All 3.0 = neutral fallback (judges don't fire in mock mode without API keys). This row exists to lock the schema + prove the harness works end-to-end.

## What the next run should produce

When the operator runs `--mode api` with real keys (estimated $5-10):
- All `clip_*_mean` columns populated (real qwen3-vl-plus scores per rubric)
- `prompt_align_*` populated (real prompt_judge scores)
- `movie_*` populated by deepseek-chat over the per-clip JSON
- `weakest_seam` set to a pair index (1-N) when one stands out
- `cost_usd` reflects real billed cost (~$0.05/movie at current model picks)

Compare api row to this mock row only on schema sanity, not score values.

## Future runs that should append rows

Each meaningful change should produce a labeled row:
- `post-rubric-tightening` — after we tighten the cheap-judge rubric per Phase 7.1.1 calibration findings
- `post-wan-2.7-trial` — after Stream B's 7.5b A/B (if Wan is plumbed)
- `post-stitch-xfade` — after Stream B's 7.7 lands
- `post-real-cycle-1` — first real-API run on real Olga photos (the actual product validation)

Each row's `run_label` should be a short slug; the timestamp + model_versions disambiguate.

## Rules

1. Append-only — never edit prior rows. Mistakes get a corrective row with `run_label="correction-..."`.
2. Mock-mode rows are valid for schema + smoke validation but NOT for quality comparison.
3. Real-API rows must include `cost_usd` for billing audit.
4. If you change CSV schema, write a migration row + bump `tools/eval_runner.py` version comment.
5. Keep the file under git so trends are reviewable.

## Related files

- `tools/eval_runner.py` — produces the CSV
- `fixtures/eval_set/{NN_slug}/metadata/expected_brief.json` — drives arc_type
- `backend/services/judges/orchestrator.py` — the judges whose scores get aggregated
- `docs/PROJECT_SCHEMA.md` — the canonical project layout fixtures conform to

## Next concrete next steps

1. Add 3 more fixtures (target 5 total per `phase_7_subplan_2_plan.md`):
   - `03_travel_diary/` — different places + same travelers
   - `04_event_recap/` — wedding / single day
   - `05_day_in_life/` — hours of one day
2. Run first `--mode api` baseline (~$5-10) when the operator decides
3. After Stream B's 7.5b lands: re-run with `model_versions` reflecting Wan 2.7
4. After Phase 7.3 calibration: tighten rubric thresholds based on Opus-vs-cheap-model agreement data
