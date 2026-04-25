# Phase 7 — Sub-Plan 1: Three-tier judge prototypes

**Status:** pending
**Size:** 2 days
**Depends on:** none (this is the foundation)
**Unblocks:** 7.2, 7.3, and the eval gate of every later sub-plan

## Goal

Ship three callable judge services — `prompt_judge`, `clip_judge`, `movie_judge` — that take their respective inputs and return a `judge_score` envelope (contract in `phase_7_flow.md`). Wire them into the pipeline behind a `JUDGES_ENABLED` env flag (default off in CI mock; on for real-API runs). Mockable in tests, callable in real runs. No UI work — pure backend services.

## Inputs / outputs

**Inputs**
- API keys (Gemini already plumbed; check if Qwen/V4 needed)
- Image data + prompt text + optional video frames

**Outputs**
- `backend/services/judges/prompt_judge.py` — sees `(image_a, image_b, prompt) → judge_score`
- `backend/services/judges/clip_judge.py` — sees `(prompt, mp4_path or 3 sampled frames) → judge_score`
- `backend/services/judges/movie_judge.py` — sees `(per_clip_judges, story_arc, brief) → judge_score`
- Tests against mocked LLM responses
- One real-API smoke test per judge (pytest mark `slow_real`)

## Step list

### 1. Module skeleton + envelope contract
- Create `backend/services/judges/__init__.py` exporting all three judges
- Add Pydantic model `JudgeScore` matching `phase_7_flow.md` § contracts
- All three judges return `JudgeScore` instances
- Validation: pytest imports the module without error

### 2. `prompt_judge` implementation
- **Model:** Gemini 2.5 Flash-Lite (cheapest vision per memory rule)
- **Rubric prompt:** "Given image A, image B, and the proposed motion prompt: rate prompt-image alignment 1-5. Does the prompt describe a plausible motion between these frames? Is the prompt grounded in what's actually visible?"
- **Output:** `prompt_image_alignment` score; null other dims
- Test: 3 mock cases (good prompt → 4-5, vague prompt → 2-3, hallucinated prompt → 1-2)
- Real-API smoke: 1 call against a known fixture, score in [1,5]

### 3. `clip_judge` implementation
- **Model:** start with Gemini 2.5 Flash (cheap + vision); benchmark Qwen3-VL-Plus as alternative
- **Input handling:** sample 3 frames at 0.2s, 2.5s, 4.5s of the 5-second clip (use existing ffmpeg helper or build it)
- **Rubric prompt:** "Rate visual quality 1-5. Anatomy intact: yes/no. Style consistent with prompt: 1-5. Brief reasoning."
- Test: 3 mock cases (good clip, anatomy break, style mismatch)
- Real-API smoke: 1 call against the wet-test `seg_1_to_2.mp4`

### 4. `movie_judge` implementation
- **Model:** DeepSeek V4 Flash (text-only, sees JSON of per-clip judges + story arc + brief)
- **Rubric prompt:** "Given these per-clip judge results, the story arc paragraph, and the brief: rate story coherence 1-5, character continuity 1-5, emotional arc 1-5. Identify the weakest seam (which pair index 1-5). One paragraph reasoning."
- Note: vision-free — operates over judge JSON only. Cheap.
- Test: 3 mock cases (coherent story, broken middle, character drift)
- Real-API smoke: 1 call against the wet-test movie's pretend-judge results

### 5. Pipeline wiring (behind flag)
- Add `JUDGES_ENABLED=auto|on|off` env var (`auto` = on if API keys present, off otherwise)
- In `pipeline_runs/.../run.json`, add `judges` section per `phase_7_flow.md` shape
- `prompt_judge` runs in the prompts stage **before** Kling submit (gate point — rejects/regens if score <2)
- `clip_judge` runs after each Kling clip downloads
- `movie_judge` runs after stitch
- Pipeline failure on judge errors: log + skip, don't block the run (this is a quality layer, not correctness)

### 6. Cost meter
- Each judge logs `cost_usd` to `run.json`
- Surface running total in pipeline logs
- Used by 7.2 eval harness for cost-per-movie metric

### 7. Tests
- `tests/backend/test_judges.py` — unit tests with mocked LLM responses
- `tests/backend/test_judges_real.py` — pytest-marked `slow_real`, requires keys, runs 1 call per judge
- Coverage target: each judge's prompt construction + response parsing

## Validation gates

1. **Logical:** all unit tests green; 3 real-API smoke tests pass when run with `pytest -m slow_real`
2. **General design:** advisor pass — confirm contract envelope is forward-compatible (new dims can be added without breaking 7.2)
3. **Working:** run real pipeline on the cat-astronaut wet-test fixtures with `JUDGES_ENABLED=on`; `run.json` has populated `judges` section

## Open questions

| Q | Default proposal | Decide when |
|---|---|---|
| `clip_judge` model — Flash vs Qwen3-VL? | Try both; pick by cost-per-call after step 3 benchmark | Step 3 |
| Frame sampling rate for `clip_judge` | 3 frames at 0.2s, 2.5s, 4.5s | Step 3 |
| Failure mode if judge errors | Log + skip, don't block run | Locked here |
| Where to plumb FAL_KEY-like env var for new vendors (Qwen, V4) | Add `X-Qwen-Key`, `X-DeepSeek-Key` headers in Settings during 7.4 UI work; for 7.1 use env vars only | Step 1 |

## Rollback / failure mode

If a judge consistently produces nonsense scores on real fixtures:
1. Iterate the rubric prompt 2-3 times.
2. If still nonsense, switch the underlying model (e.g. Flash-Lite → Flash → Qwen3-VL-Plus).
3. If still nonsense, the rubric definition is wrong — re-design the rubric with operator review.

Don't ship a judge that gives random scores; downstream decisions (re-rolls, eval gates) all depend on the score signal being real.

## Memory pointers

- `~/.claude/projects/.../memory/reference_model_prices_2026_04.md` — for model picks
- `~/.claude/projects/.../memory/feedback_model_selection.md` — old+cheap-first rule
- `phase_7_flow.md` — `JudgeScore` envelope contract (immutable after this sub-plan)
