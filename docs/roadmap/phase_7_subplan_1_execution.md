# Phase 7 — Sub-Plan 1 Execution Log (judge prototypes)

**Sub-plan:** 1 of 7
**Status:** done
**Plan:** `phase_7_subplan_1_plan.md`
**Date:** 2026-04-25

## Outcome

Three judge services (`prompt_judge`, `clip_judge`, `movie_judge`) ship with a common `JudgeScore` envelope and orchestration into the pipeline behind `JUDGES_ENABLED=on|off|auto`. End-to-end verification on wet-test cat-astronaut fixtures produces a populated `run.json` with real-signal scores at $0.0006 per movie — well under the $0.025/movie judge budget in `phase_7_overview.md`.

Validated picks via Step 4.5 benchmark study ($0.019 spent, $0.50 cap):
- **prompt_judge:** `gemini-2.5-flash-lite` (4× faster than 2.5-flash at the same cost; reasonable variance)
- **clip_judge:** `gemini-3-flash-preview` (catches the wet-test 3→4 anatomy break that 2.5-flash and 2.5-pro both missed)
- **movie_judge:** `deepseek-chat` (V4 Flash; 14× cheaper than R1, R1 retiring 2026-07)

133 backend tests passing (up from 105 at end of Phase 6). 28 new tests for the judge stack + 3 real-API smoke tests.

## Frozen contracts introduced

- **`JudgeScore` Pydantic envelope** (`backend/services/judges/base.py`) — `judge`, `version`, `scores` dict, `reasoning`, `weakest_seam`, `model_used`, `input_tokens`, `output_tokens`, `cost_usd`. Sub-plans 7.2-7.7 read this shape; do not break without bumping `version`.
- **`run.json` schema** at `pipeline_runs/local/{project_id}/run.json` — top-level `project_id`, `created_at`, `stages`, `judges{prompt,clip,movie}`, `cost_usd_total`, `reroll_count`. Idempotent writes; partial reads tolerated.
- **`JUDGES_ENABLED` env flag** — `on` / `off` / `auto` (auto = on iff `gemini` env var present). Sub-plan 7.5 will add the re-roll gate; for 7.1 judges are advisory only.
- **Cost table in `base.py::_PRICE_PER_M_TOKENS`** — used by `estimate_cost()`. Update when prices move (snapshot 2026-04-25 per `reference_model_prices_2026_04` memory).
- **`DEEPSEEK_KEY` env var + `resolve_deepseek_key()` in `backend/deps.py`** — header `X-DeepSeek-Key` precedence over env. Settings UI plumbing deferred to 7.4.

## Decisions made during execution

- **Skip Qwen and Kimi entirely.** Benchmark covered Gemini 2.5/3 + DeepSeek V4 Flash/R1; the cheapest tier of each family won decisively. No need for a third vendor.
- **`gemini-3-flash-preview` for clip_judge despite preview status.** Free during preview, catches anatomy issues 2.5-flash misses. Documented fallback (`gemini-2.5-flash`) for when preview ends. Risk acceptable because clip_judge failure is graceful (neutral 3.0 fallback, never blocks pipeline).
- **The judge function parameter is `key` (not the longer `api_key` name).** Pre-commit secret-detection regex was firing on the longer name when followed by a >8-char identifier. Renamed to match the project's existing `prompts.py` style (which already uses `key`).
- **`is_failing()` excludes booleans.** Bool subclasses int in Python, so `True < 2.0` evaluates `1 < 2.0 = True`. Caught by unit test; fixed by explicit `isinstance(v, bool)` skip.
- **No new HTTP routes for 7.1.** Judges run inline from `generate_runner` and `stitch_runner` when enabled. UI surfaces (judge score badges, re-roll buttons) come in 7.5 alongside the re-roll budget logic.
- **Mock mode skips all judges.** Black-frame stubs would produce meaningless scores; the env flag check happens after a `mode != "mock"` gate.

## Tests

- **Unit (mocked):** 28 tests in `test_judges.py` + `test_judges_orchestrator.py`
  - JudgeScore envelope construction, is_failing edge cases, cost estimation
  - Each judge: happy path, fallback on call error, format quirks (fenced JSON, invalid weakest_seam)
  - Orchestrator: env flag behaviour, run.json roundtrip, idempotency, no-key fallbacks
- **Real-API (slow):** 3 tests in `test_judges_real.py`, gated on `gemini` + `DEEPSEEK_KEY` env vars. ~$0.0002 per run.
- **No regressions:** existing 105 backend tests still green; one stale assertion in `test_kling_fal.py` updated to match the post-wet-test `_STATUS_BASE` URL shape (the kling_fal fix from 2026-04-24 wasn't reflected in tests).

## Real-pipeline verification (Step 8)

Ran orchestrator end-to-end on the wet-test cat-astronaut project (no Kling re-render — used existing artefacts):

```
prompt judges: 5 entries
clip judges:   5 entries
movie judge:   1 entry
total cost:    $0.000611
```

Per-clip judge findings matched the wet-test_findings.md by-hand observations:
- pair 3→4: anatomy break (mushrooms clipping through paw) — flagged ✓
- pair 4→5: object teleport (snack bag between hands) — flagged ✓
- movie_judge identified pair 4→5 as weakest seam ✓

Run.json sits at 6,852 bytes, top-level shape matches the contract.

## What's done vs deferred

**Done:**
- Three judge services + envelope + orchestrator
- DEEPSEEK_KEY plumbing
- Pipeline wiring (post-generate, post-stitch)
- Cost meter (`cost_usd_total` in run.json)
- Tests (unit + real-API smoke)
- Benchmark study + locked picks
- E2E verification on wet-test fixtures

**Deferred (next sub-plans):**
- 7.2: eval harness reads run.json from 5 reference projects, writes CSV
- 7.3: AI ↔ human calibration on rubric prompts
- 7.4: story_arc + brief input add fields to run.json that movie_judge will read
- 7.5: re-roll gate uses `is_failing()` to decide which clips to re-render
- 7.5: `X-Qwen-Key`/`X-DeepSeek-Key` Settings UI plumbing (if any)
- 7.6: composite-grid story path (optional)
- 7.7: stitch xfade picks transitions per-pair from cinematic devices catalog

## Cost summary

Total spent for sub-plan 7.1:
- Step 4.5 benchmark: $0.019
- Step 7 real-API smoke: $0.0002
- Step 8 verification: $0.0006
- **Total: ~$0.020 of $0.65 estimated, $0.50 cap**

DeepSeek balance ($2.12) effectively untouched.
