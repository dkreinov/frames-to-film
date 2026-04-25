# Phase 7 — Flow: how sub-plans hand off to each other

This doc lives between `phase_7_plan.md` (the master) and the per-sub-plan `phase_7_subplan_N_plan.md` files. It defines the **data contracts and ordering** that bind the seven sub-plans together so each one knows what to produce and what to consume.

## Dependency graph

```
                    ┌────────────────────────┐
                    │  7.1 Judge prototypes  │
                    │   (no dependencies)    │
                    └────────────┬───────────┘
                                 │
                                 ▼
        ┌───────────────────────────────────────────┐
        │  7.2 Eval harness (test set + runner)     │
        │   needs: judges from 7.1                  │
        │   produces: eval_runs.csv baseline row    │
        └────────────────────┬──────────────────────┘
                             │
                             ▼
        ┌───────────────────────────────────────────┐
        │  7.3 AI ↔ human calibration               │
        │   needs: eval harness, USER TIME (1-2 hr) │
        │   produces: refined judge rubric prompts  │
        │             agreement metric ≥ 70%        │
        └────────────────────┬──────────────────────┘
                             │
                             ▼
        ┌───────────────────────────────────────────┐
        │  7.4 Story arc + brief + story writer     │
        │   needs: calibrated judges                │
        │   produces: story.json artifact + UI      │
        │             eval delta vs baseline (↑)    │
        └────────────────────┬──────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────────┐  ┌──────────────┐
        │  7.5     │  │  7.6 (opt)   │  │  7.7 Stitch  │
        │  Devices │  │  Web-sub     │  │  polish      │
        │  catalog │  │  story path  │  │  (xfade)     │
        └──────────┘  └──────────────┘  └──────────────┘
```

## Frozen contracts (cross-sub-plan)

These contracts must not change without a written migration note. Each sub-plan's `_execution.md` records contracts it introduces; later sub-plans must respect them.

### `judge_score` — common output shape (introduced by 7.1)

Every judge returns the same JSON envelope so the eval harness can aggregate:

```json
{
  "judge": "prompt_judge | clip_judge | movie_judge",
  "version": "v1",
  "scores": {
    "story_coherence": 4.2,           // movie_judge only; null otherwise
    "character_continuity": 4.5,      // movie_judge only; null otherwise
    "visual_quality": 3.8,            // clip_judge + movie_judge
    "anatomy_ok": true,               // clip_judge only
    "prompt_image_alignment": 4.1,    // prompt_judge only
    "emotional_arc": 4.0              // movie_judge only
  },
  "reasoning": "...one paragraph...",
  "weakest_seam": null,               // movie_judge: identifies worst pair index
  "model_used": "gemini-2.5-flash-lite",
  "input_tokens": 845,
  "output_tokens": 120,
  "cost_usd": 0.00041
}
```

Sub-plans 7.2 (harness) and 7.3 (calibration) **read** this shape. Sub-plans 7.4–7.7 **trigger** judges and read scores. Don't break it.

### `pipeline_run.json` — per-project run record (extended in 7.2)

`pipeline_runs/local/{project_id}/run.json` exists today. 7.2 adds:

```json
{
  "project_id": "...",
  "created_at": "2026-04-26T14:30:00Z",
  "story_arc_type": "life-montage",     // 7.4 adds
  "brief": {                             // 7.4 adds
    "subject": "Sarah, age 5 to 50",
    "tone": "nostalgic",
    "notes": "..."
  },
  "story": {                             // 7.4 adds; can be null pre-7.4
    "arc_paragraph": "...",
    "pair_intents": [
      {"from": 1, "to": 2, "device": "age-match-cut", "intent": "..."}
    ]
  },
  "stages": {
    "prepare": {...},
    "prompts": {...},
    "videos": {...},
    "stitch": {...}
  },
  "judges": {                            // 7.1 introduces; populated 7.2 onward
    "prompt": [/* one per pair */],
    "clip":   [/* one per pair */],
    "movie":  {/* one entry */}
  },
  "cost_usd_total": 0.51,
  "reroll_count": 0
}
```

### `cinematic_device` — catalog entry shape (introduced by 7.5)

```yaml
- id: age_match_cut
  name: Age match cut
  description: Hold on the same facial feature (eyes, smile) of person aging across frames; dissolve preserves identity.
  applicable_arcs: [life-montage, event-recap]
  required_image_hints:
    - both frames contain the same person
    - faces visible
  prompt_template: |
    Open on close-up of {subject_feature} in image A.
    Hold for 1 second. Slow dissolve to image B preserving
    the same {subject_feature} centred in frame.
    Camera: locked, no movement.
  ffmpeg_xfade: fade           # for sub-plan 7.7
  duration_s: 5
```

Story writer picks `id`, prompt writer fills in `{subject_feature}` from image content. Sub-plan 7.7 reads `ffmpeg_xfade` to apply the right transition between clips.

## Ordering rationale (why this sequence)

### 7.1 → 7.2 → 7.3 first (eval foundation)

Without judges + harness + calibration, every later upgrade is a vibes-check. We pay an upfront 4-6 day cost to make all subsequent quality work measurable. Worth it.

The order within: 7.1 (judge code) before 7.2 (uses judges) before 7.3 (refines judge prompts based on 7.2 output).

### 7.4 next (single biggest quality lever)

Story-aware prompts are the biggest perceived-quality lift in the whole phase. Doing them after the eval foundation means we can prove the lift; doing them before would be wasted measurement opportunity.

### 7.5 right after 7.4 (cinematic devices)

Cinematic devices are useless without story context to drive choices. Story writer (7.4) chooses devices; prompt writer (7.5) applies templates. 7.5 needs 7.4's `pair_intents` shape.

### 7.6 + 7.7 in parallel at the end

Both are polish, neither blocks the other. 7.6 is optional/v1.1 for the service stage (operator already has API budget). 7.7 is must-have for the cross-fades because hard cuts undermine the cinematic-device work in 7.5.

## What ships with each sub-plan

| Sub-plan | New files | Modified files | New UI | Tests |
|---|---|---|---|---|
| 7.1 | `backend/services/judges/__init__.py`, `prompt_judge.py`, `clip_judge.py`, `movie_judge.py` | `backend/main.py` (env flag), `backend/deps.py` (new key resolvers if Qwen/V4 added) | none | unit (mocked LLM), 1 integration |
| 7.2 | `fixtures/eval_set/` (5 projects), `tools/eval_runner.py`, `eval_runs.csv` | `pipeline_runs` schema (extend `run.json`) | none | smoke: runner produces a CSV row |
| 7.3 | none (pure prompt iteration on existing judges) | `services/judges/*.py` rubric prompts | none | calibration log committed |
| 7.4 | `backend/services/story.py`, `data/story_arcs/*.yaml` (5 templates) | UploadScreen, GenerateScreen, new StoryReviewScreen | Upload mods, **Story Review (new)** | vitest, Playwright, backend |
| 7.5 | `data/cinematic_devices.yaml` (~15), `backend/services/prompt_writer.py` (transition-aware) | StoryReviewScreen (show device picks), prompts pipeline | minor (transition pills) | unit, eval gate |
| 7.6 | `backend/services/grid_compose.py`, story-source toggle UI | UploadScreen | Source toggle, paste UI | unit, manual smoke |
| 7.7 | ffmpeg xfade integration in `stitch.py` | stitch.py | none (output mp4 only) | golden frame compare |

## Cost & time budget per sub-plan

| Sub-plan | Days | Eval cost added per movie | Wall-clock to first eval verdict |
|---|---|---|---|
| 7.1 | 2 | +$0.018 (3 judges per movie) | n/a |
| 7.2 | 1-2 | $2.50 per full eval run (5 movies × $0.50) | ~30 min |
| 7.3 | 1-2 (incl. user time) | $0 (pure prompt iteration) | n/a |
| 7.4 | 2-3 | +$0.01 (story call) | 1 eval run after merge |
| 7.5 | 2-3 | $0 (pipeline already paid) | 1 eval run after merge |
| 7.6 | 2 | -$0.01 for sub users | n/a |
| 7.7 | 2 | $0 for cross-fade; +$0.05 if music bed (deferred) | 1 eval run after merge |
| **Total** | **12-16** | **~$0.50 typical / $0.92 ceiling per movie** | — |

## Eval gates (must pass to call a sub-plan done)

- **7.1**: 3 judge services callable; mocked tests pass; one real-LLM smoke per judge.
- **7.2**: Eval runner walks 5 fixtures, writes CSV row with all rubric dims populated, no crashes.
- **7.3**: Cohen's kappa or simple agreement % ≥ 70% on rubric agreement vs operator scoring.
- **7.4**: `story_coherence` median across 5 fixtures rises by **≥ 0.5** vs 7.2 baseline. No other rubric dim regresses by >0.3.
- **7.5**: `visual_quality` rises ≥ 0.3 AND `story_coherence` holds or rises. Re-roll rate ≤ 20%.
- **7.6** (optional): functional path; user can complete a movie via web-sub story step in ≤ 15 min.
- **7.7**: Visual continuity of stitched output passes operator review (no jarring cuts on age-match transitions).

## Open questions still to resolve before each sub-plan starts

| Sub-plan | Open question | Decide by |
|---|---|---|
| 7.1 | Which model for `clip_judge` — Gemini 2.5 Flash or Qwen3-VL-Plus? | Sub-plan 7.1 step 1 (try both, pick by cost-per-call benchmark) |
| 7.2 | Composition of test set — 5 from user's library or 5 synthetic? | 7.2 kickoff (user picks) |
| 7.3 | How many calibration cycles before declaring done? | 7.3 step 3 (cap at 3 cycles, accept best) |
| 7.4 | Default story-source: API or web-paste? | **Phase 7 master plan, decision #1** — current proposal: API auto |
| 7.4 | Story arc default: life-montage or 3-act? | **Phase 7 master plan, decision #5** — current proposal: life-montage |
| 7.5 | Catalog scope: 15 or 25 transitions? | 7.5 kickoff (15 baseline, expand only as eval shows demand) |
| 7.7 | Music bed in v1 or punt? | **Phase 7 master plan, decision #4** — current proposal: punt to v1.1 |

## Rollback plan if eval gate fails on a sub-plan

If 7.4 ships but eval drops `story_coherence` instead of raising it:

1. Don't merge. Iterate on the story-writer prompt or template.
2. If 3 iterations don't move the needle, surface the problem to advisor and consider switching the story model (e.g. Gemini 2.5 Pro → 3 Pro per the model-selection memory rule).
3. If still stuck, the assumption that "story-aware prompts lift quality" is wrong. Fall back to a simpler approach: per-pair prompts that share a common style preamble.

Same pattern applies to 7.5 and 7.7. Eval is the arbiter, not vibes.

## What this doc explicitly does not cover

- Per-sub-plan implementation steps (those live in each `phase_7_subplan_N_plan.md`)
- UI design (lives in stitch designs + per-sub-plan plans for 7.4/7.5/7.6)
- Stage 3 (SaaS) concerns — explicitly out of scope per `project_business_model.md`
