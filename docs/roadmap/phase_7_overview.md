# Phase 7 — Quality: story-aware pipeline + judge-driven eval

**Status:** pending (this is the overview; formal `phase_7_plan.md` to be created via `/plan` per project convention)
**Depends on:** Phase 6 close-out (parallelizable — see "Phase 6 vs 7 ordering" below)
**Origin:** `docs/wet_test_findings.md` + design discussion 2026-04-25

## What Phase 7 is

Phase 6 ships a working pipeline. Phase 7 ships a **good** pipeline. The 2026-04-25 wet test produced `full_movie.mp4` (20 MB, 25.2 s, $0.42) — technically sound, narratively empty. Five clips that don't add up to a story. Phase 7 closes that gap.

The real product target is not "cat astronaut shorts" but **life-montage videos** (the original Olga use case: child → 50s timeline). That arc has its own continuity rules and cinematic language — different from the 3-act heroic arc the wet test exercised.

### Business stage: paid service (not SaaS yet)

Phase 7 is built for **operator-driven service delivery**: the user takes paid client jobs (photos in via WhatsApp/email, mp4 out the door), drives the app themselves, delivers per-client movies. The UI must be operator-friendly, not customer self-service. SaaS concerns (auth, billing, multi-tenant, public landing page) are explicitly out of scope and deferred to Phase 8+.

This means:
- **No Vercel deploy required for Phase 7.** Localhost or a single user-owned VPS is enough.
- **Density > polish** in the operator surface (judge scores visible, re-roll buttons exposed, cost meter live).
- **Margin math:** charge ~$50–$200 per movie, cost ceiling ~$0.92 → ~99% margin. Spending $0.05 more on a better model is irrelevant if quality moves the needle.

## What Phase 7 adds

| # | Component | Purpose |
|---|---|---|
| A | **Story arc parameter** + brief input | User picks arc type (life-montage, 3-act, travel-diary, event-recap, day-in-life). Drives prompt template, continuity rule, pacing, music tone. |
| B | **Story writer** (1 call/movie) | Sees all 6 images + brief → returns 3-act/life-arc paragraph + per-pair motion intent + camera hints + continuity constraints. Top-tier model (Gemini 2.5 Pro / 3 Pro). |
| C | **Cinematic devices catalog** | Curated ~20 transitions from film grammar (match-cut, iris-in, portal-reveal, age-match-cut, camera-obstruction, dolly-zoom, etc.). Story writer picks per pair; prompt writer applies template. |
| D | **Three-tier judges** | Prompt judge (pre-render gate), clip judge (post-render, 1 re-roll budget if score <3), movie judge (post-stitch, advisory). |
| E | **Eval harness** | 5 reference projects in `fixtures/eval_set/`, auto metrics in `eval_runs.csv`, per-rubric trend tracking. **No-ship rule:** scores must move up. |
| F | **AI ↔ human judge calibration** | Both score same movies blind, iterate AI rubric prompt until agreement >70%, then AI runs autonomous batch eval. |
| G | **Web-sub story path** | Composite-grid trick (2×3 PNG with corner labels) → user uploads to gemini.google.com or chatgpt.com via existing subscription → pastes story output back. Solves image-order problem; saves API spend for sub users. |
| H | **Stitch polish** | Cross-fade transitions (ffmpeg `xfade`), optional music bed (Suno/ElevenLabs), optional TTS narration. |

## Cost ceiling per movie (target — REVISED 2026-04-25 after billing audit)

The original numbers below were based on SDK token self-reporting which
**under-counted by 10-12×** for Gemini models because their "thinking"
output tokens are NOT exposed in `usage_metadata.candidates_token_count`
but ARE billed. Verified actual rates from the 2026-04-18→25 billing
period.

| Stage | Model / cost (real) |
|---|---|
| **Outpaint/extend** | **~$1.80** (6 photos × $0.30 each via Gemini Native Image Generation) — **skipped entirely if input is already 16:9** (most modern uploads are; cat fixtures all were) |
| Story | Gemini 2.5 Pro web (sub) = $0, or API ~$0.01 |
| 5× prompt write | Gemini 2.5 Flash ~$0.05 (with thinking) |
| 5× prompt judge | Gemini 2.5 Flash-Lite ~$0.003 (low-thinking model) |
| 5× Kling render | $0.42 |
| 5× clip judge | Qwen3-VL or Gemini Flash on 3 frames ~$0.01-$0.05 |
| 1× movie judge | DeepSeek V4 Flash ~$0.005 |
| Music bed (optional) | ~$0.05 |

**Without outpaint (input already 16:9):**
- Base: **~$0.50-$0.60**
- Ceiling (1 re-roll): **~$1.00**

**With outpaint (input needs widening):**
- Base: **~$2.30**
- Ceiling: **~$2.70**

vs current $0.42 wet-test movie (which paid $3.62 for unnecessary
outpaint of already-16:9 cat photos = the bug we just fixed).

### Skip logic added 2026-04-25

`legacy/scripts/outpaint_16_9.py` now checks input aspect ratio before
calling Gemini. If within ±2% of 16:9, image is resized + saved
directly. **Saves ~$0.30 per skipped photo.** All cat fixtures hit the
skip path retrospectively — would have saved $1.80 of the $3.62 spent.

### Cost-tracking lessons

1. **SDK self-report ≠ truth.** `usage_metadata` in google-genai
   under-reports thinking tokens. Trust the billing dashboard.
2. **`gemini-3-flash-preview` is NOT free** despite the "preview" label
   — billed at $0.50/$3 per M tokens.
3. **Image generation is the killer.** Native Image Generation output
   bills at ~$26/M tokens (~$0.30 per generated image at default tile
   size). That single line was 94% of last week's bill.
4. **MAX_USD env cap** added to `tools/judge_benchmark.py` (default
   $20.00 per user policy 2026-04-25). Aborts before runaway spend.

## Sub-plan breakdown + ordering

Eval foundation lands first. Without it, every later upgrade is vibes.

| Sub-plan | Title | Size (days) | Quality lift | Dependencies |
|---|---|---|---|---|
| **7.1** | Three-tier judge prototypes (services + minimal prompts) | 2 | indirect (enables 7.2) | none |
| **7.2** | Eval harness — test set fixtures, metric runner, CSV, baseline run on current pipeline | 1-2 | indirect | 7.1 |
| **7.3** | Human/AI judge calibration cycle (1 round, agreement metric, prompt refinement) | 1-2 | indirect | 7.1, 7.2, manual user time |
| **7.4** | Story arc parameter + brief input UI + story writer service + 5 arc templates | 2-3 | **HIGH** — biggest perceived lift | 7.1-7.3 (so we can score it) |
| **7.5** | Cinematic devices catalog (~20) + transition-aware prompt writer | 2-3 | **HIGH** — second lever | 7.4 (story picks devices) |
| **7.6** | Web-sub story path: composite grid generator + paste-back UI + manual mode toggle | 2 | low (UX for sub users — **demoted to optional/v1.1 in service stage**, since operator already pays APIs and $0.01/movie savings is irrelevant vs $50 revenue) | 7.4 |
| **7.7** | Stitch polish: cross-fade + music bed + (optional) narration | 2 | medium (perception) | 7.4 |

**Total:** ~12-16 focused days. Calendar: ~4-6 weeks at normal pace.

### Ordering rationale

1. **7.1 → 7.2 → 7.3 first**: build the measurement before shipping anything you can't measure.
2. **7.4 next**: the single highest-leverage change. Story-aware prompts probably 2× perceived quality alone.
3. **7.5 right after 7.4**: cinematic vocabulary multiplies the story benefit.
4. **7.6 + 7.7 in parallel** at the end: both are polish, neither blocks the other.

## Phase 6 vs Phase 7 ordering

Phase 6 has these items left:
- README rewrite — **done** (commit `4c42a29`)
- `/app-design` pass on each screen — pending
- `/frontend-design` pass — pending
- Vercel deploy — pending

**Recommendation: do NOT ship Vercel until Phase 7 lands.** Public deploy of current quality = first-impression risk. Operator gives photos, gets a storyless 25s slideshow, churns.

**Interleave instead:**
- Skip Vercel for now. Mark Phase 6 as "review" status (waiting on quality for ship).
- Run `/app-design` + `/frontend-design` passes inside Phase 7 sub-plans 7.4 + 7.6 (since those add new UI: arc selector, brief input, story-source toggle, judge scores in review). One unified design pass on the v1 surface instead of two passes on different surfaces.
- Ship Phase 6 + Phase 7 together as a "v1 quality release" once 7.7 closes.

## Open questions / decisions to lock before /plan

1. **Default story-source**: API-auto or web-paste? (My pick: web-paste default for sub users, API toggle for power users.)
2. **Re-roll budget per movie**: 1 retry per clip? Per movie? (My pick: 1 per movie — bounds cost.)
3. **Eval cadence**: every PR? Every Phase-7 sub-plan close? (My pick: every sub-plan close minimum, pre-merge for prompt/story changes.)
4. **Music bed**: ship 7.7 with it or punt to Phase 8? (My pick: ship without; punt for v1.1.)
5. **Story arc default**: life-montage (Olga's actual use) or 3-act-heroic (broader)? (My pick: prompt user to pick on Upload screen with life-montage as default for the demo.)

## Memory pointers

- `~/.claude/projects/.../memory/project_quality_vision.md` — full architecture + why
- `~/.claude/projects/.../memory/feedback_model_selection.md` — old+cheap-first rule
- `~/.claude/projects/.../memory/reference_model_prices_2026_04.md` — current pricing snapshot

## Next action

When ready: `/plan` invocation that produces `docs/roadmap/phase_7_plan.md` and a sequenced sub-plan list. This overview becomes the input to that `/plan`.
