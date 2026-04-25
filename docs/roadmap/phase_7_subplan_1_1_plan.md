# Phase 7 — Sub-Plan 1.1: Real-asset validation against Olga reference

**Status:** in-progress (Test A pending operator's glitched-clip selection)
**Size:** 0.5–1 day total (Tests A + B + C; layered, abort early if A fails)
**Depends on:** 7.1 (judge stack shipped)
**Unblocks:** every later sub-plan (the data tells us where to invest)

## Why this exists

Phase 7.1 close-out left an open question: **does the cheap-judge stack actually catch the issues a real operator would catch?** Strong-panel benchmark (2026-04-25) revealed cheap judges miss prompt-content mismatches and falsely flag anatomy. The wet-test cat fixtures don't have an operator-grade reference movie to compare against.

But the operator (user) **already has a manually-finished 15-minute Olga movie** at `D:/Programming/olga_movie/kling_test/videos/full_movie_best.mp4` plus all the intermediate artefacts (43 extended 16:9 frames, 86 Kling-rendered clips, status.json, concat_list.txt). That's the answer key for "what good looks like."

Sub-plan 1.1 audits the auto-pipeline against that answer key **before** investing more days on 7.2 eval harness or 7.3 calibration. If the auto stack passes the audit, we move on with confidence. If it fails, the audit tells us exactly where (judge? prompt? generator?) so the next sub-plan targets the real bottleneck.

## Operator goal context

User stated 2026-04-25: aiming for **90% auto / 10% manual** workflow for paid client deliveries. Currently 100% manual. The manual finished movie is the "would-pay-for" reference. Auto-pipeline must produce comparable quality.

## Three layered tests

### Test A — Judge audit ($0)

Validates that the production cheap clip_judge (or its replacement) catches what the operator would catch.

**Inputs:**
- 5 clips from `D:/Programming/olga_movie/kling_test/videos/` selected by the operator — ideally a mix of "I know this clip has glitches" and "this clip looks fine"
- The pair-prompt that produced each (from the operator's manual prompts list, OR the prompt is unknown and we assess clip-only)

**Process:**
1. Run Opus 4.7 subagent `clip_judge` on each of the 5 clips (3-frame sampling, same as production)
2. For each: capture Opus's scores + reasoning
3. Operator labels each clip with their own verdict (ship / glitch / borderline)
4. Compare: does Opus's `anatomy_ok` and `prompt_match` low-score align with operator's "glitch" verdict?

**Output:** `docs/roadmap/phase_7_subplan_1_1_test_a.md` — table of clip ID, operator verdict, Opus verdict, agreement %

**Pass criteria:** Opus agrees with operator on ≥4 of 5 clips. (80% agreement = judge is operator-grade.)

**Cost:** $0 (Opus via session)
**Time:** ~10 minutes operator + ~2 minutes per Opus call

### Test B — Auto-prompt vs manual-prompt ($0.05–$0.50)

Validates that auto-generated prompts (Gemini Flash) match the quality of the operator's hand-crafted prompts.

**Inputs:**
- 1 frame pair from `D:/Programming/olga_movie/kling_test/` (e.g. `1.jpg` → `2.jpg`)
- The operator's manual prompt for that pair (from sidecar JSON or memory)

**Process — cheap variant:**
1. Auto-generate a prompt via Gemini Flash on the pair (~$0.005)
2. Side-by-side text comparison: operator's manual prompt vs auto prompt
3. Operator scores: how close did auto get? Is auto missing context the operator added?

**Process — real-render variant ($0.42 extra):**
1. Same as above plus
2. Render a new clip with the auto prompt via Kling (~$0.42)
3. Compare resulting clip to the existing manual-prompt clip from `kling_test/videos/`
4. Operator scores both clips: are they comparable? Does auto miss something visible?

**Output:** `docs/roadmap/phase_7_subplan_1_1_test_b.md` — text comparison + (optional) clip A/B verdict

**Pass criteria:** auto prompt produces a clip the operator would ship (or auto prompt is a clear superset of what the manual prompt contained).

**Cost:** $0.005 (text only) or $0.43 (with render)
**Time:** ~5 min text comparison, ~5 min render+watch

### Test C — Small auto movie ($2–$3)

Validates the full auto-pipeline end-to-end produces a client-grade 25-second movie.

**Inputs:**
- 6 frames selected by the operator from `D:/Programming/olga_movie/kling_test/`, spanning the timeline (e.g. baby → kid → teen → young adult → adult → 50s)

**Process:**
1. Create project: `pipeline_runs/local/olga_slice_test/`
2. Copy/symlink the 6 chosen frames to `kling_test/`
3. Skip outpaint (already 16:9) → $0
4. Auto-generate prompts (Gemini Flash, 5 prompts) → $0.005
5. Render 5 Kling clips → $2.10
6. Run Opus subagent clip_judge on each → $0
7. Re-roll any clip Opus flags badly (1 retry budget per clip, max 2 re-rolls) → $0–$0.84
8. Run Opus subagent movie_judge over the assembled judge results → $0
9. Stitch (ffconcat) → $0
10. Show operator: auto-movie vs same-frame slice from `full_movie_best.mp4`
11. Operator verdict: would I ship this to a paying client? Y/N + what's missing?

**Output:** `docs/roadmap/phase_7_subplan_1_1_test_c.md` — auto-movie path + manual-reference path + verdict + per-clip judge JSON

**Pass criteria:** operator says "yes I'd ship this" OR "yes with minor edits" (∼90% auto / 10% manual confirmed).

**Cost:** $2.10 base, $2.94 with worst-case 2 re-rolls
**Time:** ~30 minutes (mostly Kling render wait)

## Order of execution + abort rules

1. **Run A first.** If A fails (Opus disagrees with operator on ≥2 of 5 clips), fix the judge rubric before B/C. Cheaper to iterate the prompt than to render new clips.
2. **Run B next.** If auto-prompt is materially worse than manual, the operator keeps writing prompts (still 80% auto on the rest of the pipeline). Document this finding and proceed to C anyway.
3. **Run C last.** End-to-end validation. If C produces a client-grade movie, all of Phase 7's later sub-plans (eval harness, calibration, story arc, devices catalog, stitch polish) get green-lit with confidence.

## Decision rubric after C

| C's verdict | Next priority |
|---|---|
| Auto-movie is client-grade | 7.2 (eval harness for repeatability) + 7.6 (operator UX for service flow) |
| Auto-movie is bad on character continuity | 7.5b (Wan 2.7 generator A/B) — Kling is wrong for life-montage |
| Auto-movie is bad on prompt grounding | 7.4 (story arc) + rubric tightening — better prompts help |
| Auto-movie is bad on story / sequence | 7.4 (story writer) — biggest lever |
| Auto-movie is bad on visual polish | 7.7 (stitch + music) — bottom-up polish |

## Cost summary

| Test | Min | Max | Time |
|---|---|---|---|
| A — judge audit | $0 | $0 | 10 min |
| B — prompt comparison | $0.005 | $0.43 | 5–10 min |
| C — small auto movie | $2.10 | $2.94 | 30 min |
| **Total** | **$2.10** | **$3.37** | ~50 min |

Far cheaper than building 7.2/7.3 infrastructure on assumptions and finding out at the end the foundation is broken.

## Inputs the operator must provide

| Input | Test | Status |
|---|---|---|
| 5 clip filenames from `kling_test/videos/` (mix of glitched + clean) | A | **pending — operator providing now** |
| Ground-truth label per clip (operator's own verdict: ship / glitch / borderline) | A | pending |
| 1 frame pair + operator's manual prompt for that pair | B | pending |
| 6 frames spanning Olga's timeline | C | pending |

## Memory pointers

- `project_quality_vision.md` — life-montage is the real product target
- `project_business_model.md` — service stage = operator-driven, 90% auto / 10% manual
- `phase_7_subplan_1_execution.md` — judge stack we're auditing
- `strong_panel_results_2026-04.md` — why we don't trust cheap judges yet (Opus revealed grounding blindspot)

## Why this isn't a regular sub-plan

7.1.1 is a **validation** sub-plan, not an implementation one. It produces ZERO new code. Its only deliverables are markdown files (test results) that inform the priority of every subsequent sub-plan.

Treat it as roadmap insurance: half a day of clarity now is worth more than a week of building the wrong thing.
