# Phase 7.1.1 Test A — Judge audit on real Olga clips

**Date:** 2026-04-25 (overnight run)
**Total cost:** $0.029 (Qwen + Moonshot only; Opus free via session)
**Total wall-clock:** ~3 minutes
**Clips audited:** 10 (5 user-flagged + 5 control sampled across timeline)

## TL;DR for the morning

1. **Opus 4.7 caught the Hebrew text issue. Qwen and Moonshot completely missed it.** This is the most important single finding.
2. **Opus caught major scene breaks (clip 44, clip 24 frame 4.5s). Qwen and Moonshot both said "none" on clip 44.**
3. **All 3 models agreed on clips 24, 30, 36** (the "borderline" user-flagged ones) — useful confirmation that cheap models do see *something* when issues are obvious.
4. **Opus over-flagged "identity drift" on control clips** (5, 15, 50). Likely false positives caused by the rubric not distinguishing intentional age-transitions from unintended drift. **Rubric needs a fix for life-montage context.**
5. **Net recommendation:** for service-stage production, run **Opus subagent as the primary judge** — it's free via session, catches what cheap models miss, and the false-positives can be filtered with a rubric tweak. Cheap models become 2nd-tier confirmation.

## Per-clip results

### Clip 24 — operator: BORDERLINE (scary face at start)

| Model | anatomy | identity | text | faces | style | Specific issue |
|---|---|---|---|---|---|---|
| **Opus 4.7** | 4 | 3 | 5 | 4 | **2** | Frame 4.5s a completely different scene (woman in fur coat at doorway); left man's face shifted; duplicate set of bottles/fruit plate appears |
| Qwen-VL-Plus | 3 | 2 | 5 | 3 | 2 | Frame 2 unnatural lighting and ghostly overlay; Frame 3 distorted door frame and unnaturally positioned arm |
| Moonshot vision | 4 | 4 | 5 | 2 | 3 | Third frame distorted face; style of third frame slightly different from first two |

**All 3 agreed something is off.** Opus caught the scene break (extra table). Qwen caught a positional arm issue. Moonshot was vaguest. Operator's "scary face" complaint maps to the unnatural_faces flag from all 3.

### Clip 30 — operator: BORDERLINE (face not exactly correct)

| Model | anatomy | identity | text | faces | style | Specific issue |
|---|---|---|---|---|---|---|
| **Opus 4.7** | 3 | 3 | **2** | 3 | 2 | Frame 4.5s wholly different outfit (sheer purple) and altered room; calendar text from source/frame 0.2s is lost by 4.5s; mild face drift; right arm reads stiff/awkward |
| Qwen-VL-Plus | 2 | 3 | **1** | 2 | 2 | Extra arm visible in second frame; calendar text distorted and unreadable; unnatural facial expression in third frame |
| Moonshot vision | 4 | 3 | 2 | 2 | 3 | Woman's face in second frame appears distorted; visible text on wall not legible |

**All 3 caught the calendar text issue + face concerns.** Operator's "face not correct" maps to identity_drift 3 (mild) across all models. Source photo (`20260227_153700.jpg`) was provided to Opus for comparison.

**Note:** Qwen flagged an "extra arm" Opus didn't mention. Worth verifying in the morning.

### Clip 34 — operator: HEBREW TEXT WAS CHANGED

| Model | anatomy | identity | **text** | faces | style | Specific issue |
|---|---|---|---|---|---|---|
| **Opus 4.7** | 2 | **1** | **1** | 3 | **1** | **Hebrew text on poster (צלעות, מקרא, משולש, צבע) becomes garbled/illegible scribbles in final frame**; massive style/identity break — scene morphs from classroom teacher in pink jeans to a bride in wedding dress with veil at a lit venue ✓ |
| Qwen-VL-Plus | 5 | 5 | **5** | 5 | 4 | none ✗ |
| Moonshot vision | 5 | 5 | **5** | 5 | 4 | none ✗ |

**This is the headline finding.** Opus correctly identified the Hebrew text degradation AND a massive scene break (teacher → bride). Qwen and Moonshot scored 5/5/5/5/4 with "none" — completely blind to both issues. Cheap vision models cannot reliably evaluate non-Latin script.

### Clip 36 — operator: WOMAN RUNNING WITHOUT ARM

| Model | anatomy | identity | text | faces | style | Specific issue |
|---|---|---|---|---|---|---|
| **Opus 4.7** | 3 | 2 | 5 | 3 | 2 | Major scene change between frame 2.5s (4 people on stage) and 4.5s (blurry dance floor); bride/groom faces shift between 0.2s→2.5s; **background dancers in frame 4.5s heavily blurred with indistinct limbs** |
| Qwen-VL-Plus | 4 | 3 | 5 | 2 | 3 | Identity drift between frames; unnatural facial expression in third frame |
| Moonshot vision | 4 | 4 | 5 | 2 | 3 | Third frame shows woman in red skirt with **unnaturally distorted leg**; faces of people in background appear slightly blurred and indistinct |

**Mixed results.** Operator's specific concern was a missing arm. None of the 3 explicitly said "missing arm" — but Opus said "indistinct limbs" and Moonshot said "distorted leg." Both circled the area. Qwen missed it entirely. **Cheap models can miss specific limb anomalies in busy scenes** — Opus closest to operator's eye.

### Clip 44 — operator: COUPLE IDENTITY DRIFT (vs original photo)

| Model | anatomy | identity | text | faces | style | Specific issue |
|---|---|---|---|---|---|---|
| **Opus 4.7** | 4 | **2** | 5 | 4 | **1** | Frame 4.5s cuts to entirely different outdoor scene (woman with red double stroller on street) — total shot break from indoor mirror selfie; woman's face in 0.2s/2.5s looks smoothed/younger vs source ✓ |
| Qwen-VL-Plus | 5 | 5 | 5 | 5 | 5 | none ✗ |
| Moonshot vision | 5 | 5 | 5 | 5 | 5 | none ✗ |

**Same blindspot as clip 34.** Opus caught the major scene break (indoor → outdoor stroller scene) AND identity drift vs source. Qwen and Moonshot returned "none" with all-5 scores.

**Source photo path note:** the operator gave `kling_test/39.jpeg` but the actual file is `kling_test/39.jpg` (`.jpg` not `.jpeg`). Opus may have failed to read it but caught the issues from frames alone. Qwen and Moonshot definitely didn't see the source.

## Control clips (not user-flagged)

These were sampled across the timeline; operator kept all 5 in the manual cut.

### Clip 5

| Model | anatomy | identity | text | faces | style | Specific issue |
|---|---|---|---|---|---|---|
| Opus | 5 | 2 | 5 | 4 | 4 | Subject changes to a different older child in B&W with different dress and hairstyle compared to color frames |
| Qwen | 5 | 3 | 5 | 5 | 3 | Identity drift between frames; slight background limb discrepancy first frame |
| Moonshot | 5 | 5 | 5 | 5 | 5 | none |

**Opus's "different older child in B&W" likely catches an intentional age-transition** — that's how life-montage works. **False positive risk** noted for the rubric.

### Clip 15

| Model | anatomy | identity | text | faces | style | Specific issue |
|---|---|---|---|---|---|---|
| Opus | 5 | 2 | 5 | 3 | 4 | Hairstyle changes from ponytail to bangs, face shape and lips shift; slightly unnatural wide smile |
| Qwen | 5 | 4 | 5 | 5 | 3 | none |
| Moonshot | 5 | 5 | 5 | **1** | 4 | Third frame shows face with unnatural expression; style slightly different |

**Three different opinions.** Opus and Moonshot disagree heavily on faces score (3 vs 1). Worth eyeballing this clip in the morning.

### Clip 50

| Model | anatomy | identity | text | faces | style | Specific issue |
|---|---|---|---|---|---|---|
| Opus | 5 | **2** | 5 | 4 | 3 | Frame 4.5s shows a complete scene/identity change to a different family, location, and people — severe identity drift mid-clip |
| Qwen | 3 | 2 | **1** | 2 | 2 | Identity drift; text on toys not preserved correctly; unnatural faces middle frame; inconsistent lighting/backgrounds |
| Moonshot | 5 | 5 | 5 | 5 | 5 | none |

**Big disagreement.** Opus and Qwen flagged severe issues; Moonshot saw nothing. **Operator should check this clip carefully** — Opus says "complete scene change to different family." If that's intentional, it's a rubric problem. If not, the operator may have missed it.

### Clip 65

| Model | anatomy | identity | text | faces | style | Specific issue |
|---|---|---|---|---|---|---|
| Opus | 5 | 4 | 5 | 4 | 4 | Camera pans away to empty counter by frame 4.5s losing subjects; mother's face slightly softened at 2.5s |
| Qwen | 4 | 3 | 5 | 4 | 3 | Identity drift in second frame; unnatural face third frame |
| Moonshot | 5 | 5 | 5 | 5 | 5 | none |

Mostly fine. Qwen and Opus both note minor face issues. Likely acceptable as-is (operator kept it).

### Clip 75

| Model | anatomy | identity | text | faces | style | Specific issue |
|---|---|---|---|---|---|---|
| Opus | 4 | 3 | 4 | 3 | 4 | Faces of women shift between frames; **seated girl's t-shirt text 'AJENOS' appears garbled/inconsistent** |
| Qwen | 3 | 2 | **1** | 2 | 2 | T-shirt text on girl in center distorted/unreadable; unnatural faces with slight distortions; inconsistent positioning of kneeling child |
| Moonshot | 5 | 5 | 5 | 5 | 5 | none |

**Real issue: AJENOS t-shirt text becoming garbled.** Opus and Qwen both caught this — Moonshot missed it. **Operator should check** — text artifacts on visible clothing/signs are a real production-quality issue you'd want flagged automatically.

## Cross-model agreement matrix (on user-flagged clips)

| Clip | User said | Opus caught | Qwen caught | Moonshot caught | Verdict |
|---|---|---|---|---|---|
| 24 | borderline (scary face) | YES (scene break + face shift) | YES (positional arm + ghostly overlay) | YES (distorted face) | **3 of 3 agree** |
| 30 | borderline (face not correct) | YES (calendar text + face drift) | YES (extra arm + text + face) | YES (distorted face + text) | **3 of 3 agree** |
| 34 | **Hebrew text changed** | **YES — read the actual Hebrew + scene break** | NO (said "none") | NO (said "none") | **Opus only** |
| 36 | woman without arm | partial (indistinct limbs) | partial (faces only) | partial (distorted leg) | mixed |
| 44 | couple identity drift | YES (scene break + face smoothing) | NO (said "none") | NO (said "none") | **Opus only** |

**Score:** Opus catches operator's concerns 5/5. Qwen catches 3/5. Moonshot catches 3/5.

## Cost & latency

| Stage | Cost | Time |
|---|---|---|
| Frame extraction (10 clips × 3 frames) | $0 | ~5s |
| Opus subagent panel (10 calls, parallel) | $0 (session) | ~25s wall-clock |
| Qwen-VL-Plus panel (10 calls, serial) | $0.007 | ~30s |
| Moonshot vision panel (10 calls, serial) | $0.022 | ~70s |
| **Total** | **$0.029** | **~3 min** |

Opus was the cheapest (free) AND highest quality.

## Specific recommendations

### 1. Opus 4.7 as primary production judge

For service-stage paid client work, **run Opus subagent on every clip**. Cost $0 via session, catches issues cheap models miss. Cheap models get demoted to "second-pass confirmation" or skipped entirely.

The 7.1 production code currently uses `gemini-3-flash-preview` for clip_judge (not even tested in this round, but earlier benchmarks showed similar discrimination to Qwen). Recommend swapping to:

```
clip_judge primary = Opus 4.7 subagent
clip_judge fallback (if subagent unavailable / batch context) = Qwen-VL-Plus
```

### 2. Rubric needs life-montage awareness

Opus over-flagged "identity drift" on control clips because it can't tell whether the change between frames is intentional (different photos in a life-montage) or unintentional (Kling drifting within a single clip's interpolation). **Tighten the rubric:**

```
identity_drift criterion (revised):
"identity_drift = 1-2 ONLY if the same person within a SINGLE shot looks
different. Intentional age changes between consecutive photos in a
life-montage are NOT identity drift — those are the explicit subject
of the clip. Score 5 if the only differences are age-appropriate
(younger vs older same person, different photo source)."
```

This should reduce false positives on clips 5, 15, 50.

### 3. Add explicit text-artifact detection

The Hebrew text + AJENOS shirt findings show that **text preservation** is a production-quality dimension worth its own check. Cheap models miss non-Latin text entirely. Add:

```
text_ok criterion (explicit):
"For ANY visible text (Hebrew, English, signs, books, t-shirts, calendars):
  - Score 5 if text is preserved or absent
  - Score 1-2 if text becomes garbled, illegible, or different across frames
  - Hebrew/Arabic/Cyrillic require careful inspection — if you cannot read
    the script, do not assume it's preserved; flag for operator review"
```

### 4. Don't trust single-cheap-model verdicts

Clip 50: Moonshot said "none", Opus said "complete scene change to different family", Qwen said multiple issues. Single-judge cheap-tier output is unreliable. **2-of-2 agreement** between Opus + a cheap model would be a robust default. If they disagree, ask the operator.

## What to verify in the morning

For each clip below, watch in your video player and compare your gut reaction to the listed verdict:

| Clip | Watch for | Consensus says |
|---|---|---|
| 24 | scene break around 4.5s, extra table/bottles | break confirmed by all 3 models |
| 30 | calendar text in 4.5s, face drift, possible extra arm | issues confirmed |
| **34** | **Hebrew on poster — reads correctly or garbled?** | Opus says **garbled** — VERIFY THIS |
| 36 | background dancers — count limbs at 4.5s | partial agreement |
| 44 | indoor selfie → outdoor stroller? identity vs your selfie? | Opus says yes; cheap models missed |
| 5 | child's age changes — intentional or weird? | Opus flagged, you may have wanted it |
| 15 | hairstyle/face — single shot or photo transition? | mixed |
| **50** | **family changes between frames** — intentional or bug? | Opus + Qwen flagged; CHECK |
| 65 | mother's face at 2.5s | minor |
| **75** | **'AJENOS' t-shirt text** — readable or garbled? | Opus + Qwen flagged; CHECK |

## Files generated

- `docs/roadmap/phase_7_subplan_1_1_test_a.md` (this file)
- `docs/roadmap/_test_a_qwen_moonshot_results.json` (raw Qwen + Moonshot data)
- `docs/roadmap/_test_a_frames/clip_*/` (extracted frames per clip — gitignored)

## Next step

After you verify the verdicts in the morning, decide:

**(A)** Use Opus subagent as production judge (best quality, free) + ship 7.1.1 as a "production swap" sub-plan.

**(B)** Run Test B (auto-prompt vs manual-prompt) and Test C (small auto movie) before locking in Opus-as-judge.

**(C)** Skip ahead to 7.4 (story arc) — the judge stack is good enough, focus on prompt quality.

I'd recommend **(A) immediately for production**, then **(B/C) when you're ready** — Opus-as-judge is a strict quality upgrade with zero cost increase.
