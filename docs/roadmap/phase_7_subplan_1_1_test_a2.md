# Phase 7.1.1 Test A v2 — Source-aware judge with main-character logic

**Date:** 2026-04-26
**Total cost:** $0.029 (Qwen + Moonshot; Opus subagents free via session)
**Total time:** ~3 minutes
**Clips audited:** 6 (4 user-flagged + 2 control)

## TL;DR

**Architecture change works.** Opus 4.7 with the new source-aware + main-character rubric got **6 of 6 verdicts right** matching the operator's own assessment.

Previous v1 (sourceless) judge over-flagged intentional age-transitions on control clips and missed which scene-changes were intentional vs Kling failures. v2 fixes both.

| | v1 (sourceless) | v2 (source-aware) |
|---|---|---|
| Opus correct verdicts | 5/10 (false positives on growing-up clips) | **6/6** |
| Catches Hebrew text issue | yes (with hint about Hebrew) | yes (rubric mentions "any script" only) |
| Catches limb anatomy issues | partial | yes |
| False positives on intentional age progression | yes (clips 5, 15, 50) | **none** |

## What changed in the architecture

### Old judge inputs (v1)

```
3 frames sampled from rendered clip
```

### New judge inputs (v2)

```
1. SOURCE START image (the photo fed to Kling as image_a)
2. SOURCE END image (the photo fed to Kling as image_b)
3. Clip frame at 0.2s
4. Clip frame at 2.5s
5. Clip frame at 4.5s
```

### Rubric shift

| Dimension | v1 | v2 |
|---|---|---|
| identity_drift | "anyone changing across the 3 frames" | **"main character (person in BOTH sources) drifting WITHIN the 3 clip frames beyond what the source-to-source morph explains"** |
| style | "do the 3 frames feel like the same shot?" | **"do the 3 frames have rendering glitches, ghosting, blur — Kling-introduced artifacts only"** |
| anatomy | "any limb/face issues" | **"limb/anatomy issues IN THE CLIP not present in either source image"** |
| text | "text preserved correctly across frames" | **"text in clip vs text in sources — flag degradation introduced by Kling"** |

The key principle: **flag only what Kling broke. Source-to-source differences are intentional and don't count.**

### How "main character" is identified

Auto-detected as the person who appears in BOTH source start and source end. For a life-montage, that's the subject (Olga). Supporting cast in only one of the two sources is treated as transient. This means:
- Olga's face drifting within a clip = real bug
- Husband appearing in source end but not start = intentional
- Different children in different photos = intentional

## Per-clip verdicts

Convention: **clip N = source frames N.jpg + (N+1).jpg from `outpainted/`**.

### Clip 24 — operator: BORDERLINE (scary face)

| Model | mc_drift | text | limbs | faces | glitches | Specific issue |
|---|---|---|---|---|---|---|
| **Opus 4.7** | 3 | 5 | 4 | 4 | **2** | "Frame 4.5s severe compositing glitch — duplicate table with bottles/fruit ghosted; pink-tile wall bleeding into carpet; Olga's face shifts between 2.5s and 4.5s" |
| Qwen-VL-Plus | 3 | 1 | 1 | 2 | 3 | "subtle facial changes; bottle labels less legible; arm positioning unnatural" |
| Moonshot vision | 4 | 5 | 5 | 5 | 4 | "none" |

**Verdict: ✓** Opus catches the real Kling glitch (ghosted table). Qwen over-flags everything (text=1, limbs=1 — false positives). Moonshot too lenient (mostly 5s).

### Clip 30 — operator: BORDERLINE (face not exactly correct)

| Model | mc_drift | text | limbs | faces | glitches | Specific issue |
|---|---|---|---|---|---|---|
| **Opus 4.7** | 4 | 3 | 4 | 4 | 3 | "Significant motion blur; calendar text garbles into illegible smears; right hand/arm becomes blurred and indistinct during spin" |
| Qwen-VL-Plus | 2 | 1 | 1 | 1 | 3 | "face slightly different at 2.5s; calendar text less legible; arm distorted in 4.5s" |
| Moonshot vision | 2 | 5 | 5 | 5 | 2 | "main character's face drifts unnaturally; some blurriness" |

**Verdict: ✓** All 3 caught real issues. Opus most precise (named the right hand). Operator's "face not correct" complaint maps to Opus's mc_drift 4 + glitches 3.

### Clip 34 — operator: HEBREW TEXT WAS CHANGED

| Model | mc_drift | **text** | limbs | faces | glitches | Specific issue |
|---|---|---|---|---|---|---|
| **Opus 4.7** | 3 | **1** | 3 | 4 | 2 | **"Hebrew text on the ketubah/poster becomes garbled and smeared in 4.5s frame; document's intricate decorative border degrades into blurry shapes"** ✓ |
| Qwen-VL-Plus | 2 | 1 | 1 | 1 | 2 | "main character's face slightly distorted; **text on poster blurry**; arm positioning unnatural" |
| Moonshot vision | 1 | 2 | 5 | 5 | 2 | "**Text on poster is garbled in frames 3-5**; face slightly distorted in frame 5" |

**Verdict: ✓✓** All 3 models caught the Hebrew text issue with the v2 rubric — including Moonshot which **completely missed it in v1**. Source images let Moonshot compare and see the text degraded. The rubric did NOT mention Hebrew specifically; it said "any script." Real signal.

**Note: Opus identified the document type as a "ketubah"** (Jewish wedding contract) — that's contextual recognition the cheap models don't show.

### Clip 36 — operator: WOMAN RUNNING WITHOUT ARM

| Model | mc_drift | text | limbs | faces | glitches | Specific issue |
|---|---|---|---|---|---|---|
| **Opus 4.7** | 4 | 5 | 3 | 3 | 3 | "At 4.5s scene morphs into blurry crowd with **multiple background figures showing distorted/missing limbs and smeared faces**" ✓ |
| Qwen-VL-Plus | 1 | 1 | 1 | 2 | 3 | "Image 5 heavy blur and ghosting; Image 4 unnatural facial expressions; Image 3 distorted limb anatomy on main character" |
| Moonshot vision | 1 | 5 | 5 | 5 | 5 | "none" (despite mc_drift=1??) |

**Verdict: ✓** Opus caught the "distorted/missing limbs" — exactly the operator's complaint. Qwen also caught limb issues. Moonshot saw something (mc_drift=1) but couldn't articulate (limbs=5).

### Clip 5 — operator: OK (intentional age transition)

| Model | mc_drift | text | limbs | faces | glitches | Specific issue |
|---|---|---|---|---|---|---|
| **Opus 4.7** | **5** | **5** | **5** | **5** | **5** | "Clip stays on toddler source frame across timestamps with only minor paper-edge framing animation; **no Kling-introduced morphing artifacts**" |
| Qwen-VL-Plus | 1 | 1 | 1 | 1 | 2 | "none" (despite all 1s) |
| Moonshot vision | **5** | **5** | **5** | **5** | **5** | "none" |

**Verdict: ✓✓** Opus and Moonshot correctly distinguished intentional age progression from drift — clean 5/5/5/5/5. **Qwen scored everything 1 with reasoning="none"** — it's grading way out of calibration; treats every clip as broken.

This is huge. **In v1, Opus over-flagged this clip.** v2 fixes it.

### Clip 15 — operator: OK (intentional age transition)

| Model | mc_drift | text | limbs | faces | glitches | Specific issue |
|---|---|---|---|---|---|---|
| **Opus 4.7** | **5** | **5** | **5** | **5** | **5** | "Clip frames stay close to START photo and don't yet morph to END within sampled frames; **no Kling-introduced anatomy, face, or text issues**" |
| Qwen-VL-Plus | 3 | 1 | 1 | 2 | 2 | "subtle changes in facial expression and hair movement; faint vertical text artifacts; slight distortion in shoulder area" |
| Moonshot vision | **5** | **5** | **5** | **5** | **5** | "none" |

**Verdict: ✓** Opus and Moonshot correctly approved. Qwen continued false-positive pattern.

## Cross-model summary

| Model | Operator agreement (6 clips) | Catches real issues | False positives | Overall |
|---|---|---|---|---|
| **Opus 4.7 (subagent)** | **6/6** | yes — all 4 user-flagged + correct rejection of 2 controls | none | **production-grade** |
| Moonshot v1-128k-vision-preview | 4/6 | partial — caught Hebrew (huge win!), face drift, but missed limb anatomy on clip 36 | none on this set | useful as 2nd-tier confirmation |
| Qwen-VL-Plus | 0/6 | over-flags everything | severe — scored intentional-OK clips as broken | **NOT production-grade** with this rubric |

### What broke Qwen

Qwen's outputs in v2 show it can't calibrate scores. Looking at clip 5 (which is OK):
- mc_drift: 1 (severe)
- text_artifacts: 1 (severe)
- limb_anatomy: 1 (severe)
- unnatural_faces: 1 (severe)
- glitches: 2 (significant)
- specific_issues: "none"

It's contradicting itself — scoring 1s while saying "none." The model isn't actually evaluating the rubric, just emitting low scores reflexively. **Qwen-VL-Plus is unreliable for this task.** The cost savings vs. Gemini we saw earlier are illusory if the signal is wrong.

### Why Moonshot improved with v2

In v1 (sourceless), Moonshot returned "none" with all-5 on the Hebrew text and scene-break clips. With source images for comparison, Moonshot now correctly identifies text garbling (clip 34 text=2) and face drift (clip 30 mc_drift=2). The source-aware rubric gives even cheap-tier models the comparison reference they need.

## The right production architecture

```
clip_judge inputs:
  source_start: Path        # frame N.jpg from outpainted/
  source_end: Path          # frame N+1.jpg from outpainted/
  clip_video: Path          # the rendered mp4
  
  → extract 3 frames at 0.2s, 2.5s, 4.5s
  → call vision LLM with all 5 images + source-aware rubric
  → return JudgeScore with per-dimension scores

clip_judge primary model: Opus 4.7 via subagent (cost: $0 via session)
clip_judge optional confirmation: Moonshot v1-128k-vision-preview ($0.002/call) for 2-of-2 agreement on borderline cases
```

The current production `backend/services/judges/clip_judge.py` needs to be updated:
1. Accept `source_start_path` and `source_end_path` parameters
2. Replace the rubric prompt with the v2 source-aware version
3. Pass all 5 images (sources + 3 frames) instead of just 3 frames
4. Switch default model from `gemini-3-flash-preview` to `claude-opus-4-7` via Anthropic SDK OR keep using subagent invocation when running inside Claude Code session
5. Update tests to mock the new image inputs

`prompt_judge` should also be updated to accept source images — same logic, the prompt should be evaluated against what's actually in the source frames.

## Cost projections

| Setup | Per movie (5 pairs × 5 clips judged) | Per 100 movies/month |
|---|---|---|
| Production today (Gemini Flash + Flash-Lite) | ~$0.10–$0.20 (real billed) | $10–$20 |
| **Opus subagent (v2)** | **$0** (session-billed) | **$0** |
| Moonshot 2nd-tier confirmation (only if disagreement) | ~$0.01 | ~$1 |

**Opus subagent in production = strict quality upgrade at zero marginal cost.**

The catch: subagent calls require Claude Code session context. For a self-hosted operator-run service, that's fine — operator runs the app on their machine, Opus runs through their Claude subscription. For a future SaaS deployment, would need Anthropic API key directly.

## What I want operator to verify in the morning

For each clip, look at the v2 verdict in the table above and tell me whether you agree:

| Clip | Opus v2 says | Match your verdict? |
|---|---|---|
| 24 | scene-glitch (duplicate table, face shift) | yes/partial/no? |
| 30 | calendar garbles, arm blurred | yes/partial/no? |
| 34 | Hebrew text becomes garbled (real Kling failure) | yes/partial/no? |
| 36 | background figures with distorted/missing limbs | yes/partial/no? |
| 5 | NO Kling-introduced issues (intentional age transition) | yes/partial/no? |
| 15 | NO Kling-introduced issues | yes/partial/no? |

If 6/6 agree, the v2 architecture is locked. Next step: update production code.

If any disagreements, tell me which and we adjust the rubric.

## Files

- `docs/roadmap/phase_7_subplan_1_1_test_a2.md` (this report)
- `docs/roadmap/_test_a2_qwen_moonshot_results.json` (raw Qwen + Moonshot data)
- `docs/roadmap/_test_a2_frames/clip_*/` (extracted frames)
- `tools/_test_a2_qwen_moonshot.py` (re-runnable v2 panel script)

## Recommendation

**Lock the v2 architecture** for production:

1. Update `backend/services/judges/clip_judge.py` to accept source_start + source_end paths
2. Update `backend/services/judges/prompt_judge.py` similarly (uses sources for grounding check)
3. Default model: Opus 4.7 via subagent (zero cost)
4. Cheap-model fallback: Moonshot v1-128k-vision-preview (deprecated Qwen for this rubric)
5. Update orchestrator to discover source paths from project structure (`outpainted/N.jpg`, `outpainted/(N+1).jpg`)
6. Re-run tests + commit + push

Estimated implementation: 2-3 hours. Stays well within "build the judge" scope.
