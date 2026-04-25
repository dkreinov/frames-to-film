# Phase 7 — Sub-Plan 3: AI ↔ human judge calibration

**Status:** pending
**Size:** 1-2 days (most of the time is operator scoring, not coding)
**Depends on:** 7.1 (judges) + 7.2 (eval harness with baseline)
**Unblocks:** 7.4 (story arc work) — once calibrated, AI judge becomes trustworthy for autonomous eval

## Goal

Bring the AI judge's scoring into ≥70% agreement with the operator's scoring on a fixed rubric. Calibrate by iterating the rubric prompts until disagreement narrows. After this, AI judge runs autonomous eval and the operator only spot-checks.

## Inputs / outputs

**Inputs**
- 5 baseline movies from 7.2 (the `runs/post-7.1-baseline/` artefacts)
- Operator time: ~30-60 min for one round of scoring; up to 2-3 rounds total

**Outputs**
- `docs/roadmap/eval_calibration_2026-04.md` — log of agreement metrics across rounds
- Refined rubric prompts in `backend/services/judges/*.py` (committed)
- Final agreement metric ≥ 70%; if not achievable in 3 rounds, surface to advisor

## Step list

### 1. Score the 5 baseline movies — operator round
- Operator watches each of the 5 baseline movies (from 7.2 run)
- Uses a 4-dim rubric on a Google Sheet or simple form:
  - Story coherence 1-5
  - Character continuity 1-5
  - Visual quality 1-5
  - Emotional arc 1-5
- No looking at AI scores yet (blind)
- Save as `eval_calibration/round_1_human.csv`

### 2. Score the same 5 with `movie_judge` from 7.1
- Just read the `movie_judge` row already in `eval_runs.csv`
- Save as `eval_calibration/round_1_ai.csv`

### 3. Compute agreement
- Per dimension, mean absolute Δ between human and AI score
- Direction agreement: when one scores upgrade higher, does the other?
- Cohen's kappa or simple % within ±1 of each other
- Target: mean abs Δ ≤ 0.7 on 1-5 scale, or ≥ 70% within ±1

### 4. Diagnose disagreements
- For every pair where Δ ≥ 1.5, write a one-line note: what did the AI miss / over-emphasise?
- Common patterns to look for:
  - AI over-rates technical fluency, under-rates emotional resonance
  - AI under-rates continuity issues that human catches instantly
  - AI hallucinates "good story" because the prompt sounded coherent

### 5. Refine the AI judge rubric prompt
- Based on diagnosis, edit `movie_judge.py` rubric prompt:
  - Add explicit criteria the AI was missing (e.g. "Score continuity DOWN if the same character appears with different identifying features")
  - Reduce weight on dimensions the AI over-emphasised
- Re-score the same 5 movies with new prompt
- Compute agreement again

### 6. Repeat steps 1-5 up to 3 cycles
- If round 3 still <70% agreement, surface to advisor with the diagnosis log
- Possible escalations: switch judge model (V4 Flash → V4 Pro), simplify rubric, accept lower agreement and add more human-in-the-loop checkpoints

### 7. Lock the rubric prompts
- Tag the final prompts in code with `RUBRIC_VERSION = "v1"` constant
- Future changes require explicit version bump + re-calibration

## Validation gates

1. **Logical:** agreement ≥ 70% on the 5-movie set
2. **General design:** advisor pass — confirm calibration methodology is sound + rubric prompts are stable
3. **Working:** running `tools/eval_runner.py` again with the locked prompts produces scores within ±0.5 of the calibration round-N result for the same fixtures

## Open questions

| Q | Default proposal | Decide when |
|---|---|---|
| Cap on calibration rounds | 3 | Locked here |
| Agreement metric (kappa vs % within ±1) | % within ±1 (simpler, transparent) | Step 3 |
| What if 3 rounds fail | Advisor pass + accept lower bar OR switch model | Step 6 if reached |
| Recalibration cadence post-locked | Re-calibrate on every model swap or rubric change | Locked |

## Rollback / failure mode

If calibration plateaus below 70% even after 3 rounds:
- The rubric is asking for something the LLM judge can't see (e.g. emotional nuance)
- Options: (a) drop that dimension from the AI rubric, keep as human-only, (b) switch to a smarter model, (c) re-define the dimension into something more LLM-tractable
- Document the decision in `eval_calibration_2026-04.md`

## Memory pointers

- `project_quality_vision.md` — calibration approach + rubric dimensions
- `phase_7_flow.md` — `JudgeScore` envelope (this sub-plan refines the prompts that produce these scores)
