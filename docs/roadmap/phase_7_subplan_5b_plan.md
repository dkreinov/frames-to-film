# Phase 7 — Sub-Plan 5b: Video generator A/B (Kling O3 vs Wan 2.7 i2v)

**Status:** pending
**Size:** 2-3 days (adapter + eval + decision)
**Depends on:** 7.1 (judges shipped) + 7.2 (eval harness) + 7.5 (cinematic devices catalog — Wan's better cinematography-aware prompting may unlock devices Kling can't render)
**Parallel-able with:** 7.6, 7.7
**Quality lift:** **HIGH for life-montage arc** (the real product target)

## Why this exists

Wet-test (2026-04-25) shipped on **Kling O3 standard** at $0.084/s. Known weakness surfaced post-test: **character drift across clips** — the cat astronaut's appearance subtly shifts pair-to-pair because Kling treats each (image_a, image_b, prompt) tuple independently. For 3-act heroic with cats, that's tolerable. For **life-montage** (Olga's age 5-to-50 timeline — the actual product target), character drift = "this is a different person" = the premise breaks.

**Alibaba's Wan 2.7 i2v** explicitly claims:
- **First+last frame control native to a single model** (no variant URL gotchas like Kling's `_STATUS_BASE` workaround we patched)
- **Stronger character consistency across shots** (called out specifically vs Kling in independent reviews)
- Up to **15s clips at 1080p** (Kling O3 standard caps at 5s, 720p)
- Native audio output (we can ignore for now; relevant later for music bed in 7.7)
- Cinematography-aware prompting (likely better fit for our 7.5 cinematic-devices catalog)

If those claims hold up on our fixtures, Wan 2.7 is the right generator for the life-montage product, even at ~50% higher per-clip cost.

## Goal

Run a head-to-head A/B between Kling O3 std and Wan 2.7 i2v 720p on the same fixtures (wet-test cats + sub-plan 7.2 eval set when available). Score both with the production cheap-judge stack (and the strong panel from the 7.1-side experiment). Decide:

1. **Default video generator going forward** — does Wan 2.7 lift quality enough to justify ~50% cost increase?
2. **Per-arc-type override** — should life-montage use Wan 2.7 while 3-act-heroic stays on Kling?
3. **Tier choice within Wan** — 720p flat $0.625 vs 1080p flat $0.9375 (only ~50% incremental)?

## Inputs / outputs

**Inputs**
- DashScope / Alibaba Cloud Model Studio account with Wan 2.7 access (user must register; I cannot create accounts)
- 7.1 cheap-judge stack
- 7.2 eval harness + reference fixtures
- Optional: 7.1-side strong-panel experiment results (gives stronger A/B verdict)

**Outputs**
- `backend/services/wan_25.py` — Wan 2.7 adapter mirroring `backend/services/kling_fal.py` shape (functionally a drop-in `generate_pair()` replacement)
- New `Mode` value or env flag: `VIDEO_GENERATOR=kling|wan` (default kling for now; flip after eval)
- `tests/backend/test_wan_25.py` — mocked HTTP unit tests (mirror `test_kling_fal.py`)
- `tests/backend/test_wan_25_real.py` — slow_real smoke (~$0.625, gated on `DASHSCOPE_KEY`)
- `docs/roadmap/wan_vs_kling_eval_2026-XX.md` — A/B results across N fixtures with judge scores side-by-side
- Decision recorded in `phase_7_subplan_5b_execution.md`

## Step list

### 1. Vendor signup + key plumbing
- User: register at https://qwen.ai/apiplatform (or https://bailian.console.alibabacloud.com/), top up ~$10
- Add `resolve_dashscope_key()` to `backend/deps.py` (mirror DeepSeek pattern, env name `DASHSCOPE_KEY`)
- `X-DashScope-Key` header support on relevant routes (later)

### 2. Wan 2.7 adapter (`backend/services/wan_25.py`)
- Mirror `kling_fal.py` API shape:
  ```python
  def generate_pair(
      image_a: Path, image_b: Path, prompt: str,
      key: str, duration_s: int = 5, resolution: str = "720p",
  ) -> bytes: ...
  ```
- Wan API endpoint: confirm whether it's the DashScope async-task pattern (submit → poll → fetch) like Kling or sync. Adjust polling logic accordingly.
- First+last frame: pass both images natively (no separate "end_image_url" hack like Kling's data URI dance)
- Error handling: same shape as Kling (`raise_for_status`, custom `RuntimeError` for FAILED, `TimeoutError` on poll exhaustion)

### 3. Generator-selection plumbing
- Add `VIDEO_GENERATOR` env var (default `kling`)
- `generate.py` reads the flag and dispatches to the right adapter
- Keep both adapters live so A/B is a single env-var flip
- Pipeline contract unchanged — both adapters return mp4 bytes

### 4. Single-clip smoke test
- Render one wet-test pair (image 1 → image 2) on both Kling and Wan 2.7
- Cost: $0.084 (Kling already paid in wet test; just re-run) + $0.625 (Wan 720p) = ~$0.71
- Visual inspect side-by-side
- Sanity check: does Wan output match the prompt at all? Does first+last frame control work?
- If Wan smoke fails → debug before scaling up

### 5. Full A/B render across fixtures
- Re-render all 5 wet-test cat clips on Wan 2.7 720p: 5 × $0.625 = **$3.13**
- Once 7.2 eval set exists: also re-render those 5 reference projects: 5 × 5 × $0.625 = **$15.63**
- Total A/B render budget: ~$20 (vs current Kling cost of ~$2-4 for the same)
- Save outputs side-by-side under `pipeline_runs/local/{project_id}/wan_test/` (parallel to existing `kling_test/`)

### 6. Eval pass
- Run cheap-judge stack on both Kling and Wan outputs for every fixture
- Run strong-judge panel (from 7.1-side experiment) on a subset for higher confidence
- Aggregate into `wan_vs_kling_eval_2026-XX.md`:
  - Per-pair: visual_quality, anatomy_ok, prompt_match, character_continuity_inferred
  - Per-movie: story_coherence (when story.json available), weakest seam comparison
  - Cost delta per movie

### 7. Decision rubric

Decision criteria (must all hold to switch default to Wan):
- **Character continuity** mean across fixtures: Wan ≥ Kling + 0.5
- **Visual quality** mean: Wan ≥ Kling - 0.2 (slight regression OK if continuity wins)
- **Anatomy break rate**: Wan ≤ Kling
- **Cost-per-perceived-quality**: ratio of (continuity + visual mean) / cost makes Wan ≥ Kling × 0.7

If only character continuity wins decisively but visual quality regresses sharply: **per-arc override** — Wan for life-montage / event-recap, Kling for 3-act-heroic / day-in-life / travel-diary. Configurable via `story_arcs/{arc}.yaml`.

### 8. Documentation
- `docs/roadmap/phase_7_subplan_5b_execution.md` close-out with verdict
- Update `docs/roadmap/phase_7_overview.md` cost ceiling per movie (may rise)
- Update memory `project_quality_vision.md` if Wan becomes the default

## Validation gates

1. **Logical:** unit tests on Wan adapter green; smoke test produces a valid mp4 with `ftyp` atom
2. **General design:** advisor pass on the dispatch shape — confirm both adapters expose identical contract
3. **Working:** end-to-end A/B render on at least 1 fixture project in each generator
4. **Eval delta:** quantitative results in `wan_vs_kling_eval_2026-XX.md` covering all decision-rubric dimensions
5. **No regressions:** Kling path still works after dispatch refactor; existing 133 backend tests stay green

## Open questions

| Q | Default proposal | Decide when |
|---|---|---|
| Default resolution: 720p or 1080p? | 720p (50% cheaper, sufficient for 25s movies) | Step 5 |
| When does the eval set exist for the bigger A/B run? | After 7.2 ships | 7.2 close |
| Should we A/B Sora 2 / Veo 3.1 Lite too? | Defer — Wan 2.7 is the most directly comparable to Kling (same first+last frame native shape) | Locked here |
| What if Wan 2.7 fails badly? | Stick with Kling, document the verdict, close 5b | Step 4-7 |
| Audio? | Defer entirely (music bed is a 7.7 question) | Locked |

## Rollback / failure mode

If Wan 2.7 doesn't beat Kling on the rubric:
1. Document why — was it generic quality? Specific weakness? Style mismatch?
2. Keep adapter alive but flip default back to Kling
3. Re-test in v1.1 if Wan publishes a new model version

If Wan 2.7 wins decisively but cost ceiling spooks the user:
1. Flip default to Wan
2. Add per-arc override logic so 3-act-heroic / day-in-life can stay on Kling
3. Update `phase_7_overview.md` cost ceiling — likely +$3-5 per movie

If Wan API is too unstable (frequent failures, queue length issues):
1. Keep on Kling for production reliability
2. Re-test in 6 months when Wan API matures

## Memory pointers

- `project_quality_vision.md` — character continuity is the biggest known weakness for life-montage; this sub-plan addresses it
- `project_business_model.md` — service stage margin is fine even at $4.69/movie generator cost ($50 revenue → ~90% margin still)
- `feedback_model_selection.md` — old+cheap-first applies to judges; for the generator that drives perceived quality, it's worth paying more if eval proves the lift
- `phase_7_flow.md` — `JudgeScore` envelope unchanged; A/B uses existing eval shape

## Decision deferred until experiment runs

This sub-plan **does not commit to switching to Wan 2.7.** It commits to **measuring whether to switch.** The verdict comes from data, not from blog-post claims about character consistency. We've learned (Step 4.5 benchmark in 7.1) that vendor marketing and eval results can disagree.
