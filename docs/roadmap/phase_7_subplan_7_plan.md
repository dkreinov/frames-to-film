# Phase 7 — Sub-Plan 7: Stitch polish (cross-fade + optional music)

**Status:** pending
**Size:** 2 days (cross-fade only); +2 days if music bed included
**Depends on:** 7.5 (cinematic devices catalog with `ffmpeg_xfade` mapping)
**Quality lift:** medium (perceived polish — undermines 7.5 if not done)

## Goal

Replace today's hard-cut ffconcat with cinematic-device-aware transitions (`ffmpeg xfade`). Each clip pair's stitch transition matches the device the story writer picked in 7.5 (e.g. age_match_cut → fade, iris_in → circleopen, whip_pan → wipeleft). Optionally add a music bed; punt to v1.1 per `phase_7_plan.md` decision #4.

## Inputs / outputs

**Inputs**
- 5 clip mp4s from Kling
- `story.pair_intents[i].device` from 7.4-7.5
- `cinematic_devices.yaml[device_id].ffmpeg_xfade` flag

**Outputs**
- Updated `backend/services/stitch.py`:
  - Reads device per pair, looks up xfade flag, applies it between clips
  - Falls back to `fade` if device unknown
- Optional (deferred): music bed mixed into final mp4
- New: golden frame comparison test — ensures transitions render visually distinct

## Step list

### 1. ffmpeg xfade mapping
- Confirm xfade flag for each catalog device (in 7.5's `cinematic_devices.yaml`)
- Common mappings:
  - `cross_dissolve` → `fade`
  - `age_match_cut` → `fade` with longer duration (1s)
  - `iris_in` → `circleopen`
  - `iris_pinhole` → `circleclose` then next clip
  - `whip_pan` → `wipeleft` or `wiperight`
  - `fade_to_black` → `fadeblack`
  - `smash_cut` → no xfade (instant cut)
  - `photo_frame` → `pixelize` or custom (stretch goal)
- Add fallback: any device without a flag uses `fade`

### 2. Refactor `stitch.py`
- Replace ffconcat-only path with xfade-driven path
- For N clips with N-1 transitions: build ffmpeg filter graph of N-1 xfade segments
- Each xfade has: source clips, transition flag, duration (default 0.5s, override per device template)
- Audio: passthrough silent for now (music bed handled separately if at all)

### 3. Per-device duration override
- `cinematic_devices.yaml[device_id].xfade_duration_s` controls how long the transition takes
- Slow transitions (age_match_cut, cross_dissolve): 1s
- Fast transitions (whip_pan, smash_cut): 0.2s
- Default: 0.5s

### 4. Tests
- Golden frame test: stitch a known pair-set with all 15 transitions, save 1 frame at the transition midpoint per pair, compare against committed goldens (regenerate manually after visual approval)
- Smoke test: stitch 5 clips with mixed transitions runs without crash + output mp4 has expected duration (sum of clip durations + transitions accounting for overlap)
- Negative test: stitch with unknown device id falls back to `fade` cleanly

### 5. (Optional) Music bed integration — DEFER
- `services/music.py` calls Suno or ElevenLabs API
- Auto-generates a music bed sized to the movie length + arc tone
- Mixed into stitch ffmpeg call
- Cost: ~$0.05/movie via ElevenLabs Music API
- **Decision:** punt to v1.1 per phase_7_plan.md decision #4. Document as TODO.

### 6. (Optional) TTS narration — DEFER
- Even further out. Punt to Phase 8+.

### 7. Eval gate run
- `tools/eval_runner.py --label "post-7.7"`
- Target: `visual_quality` ↑ ≥ 0.2 vs post-7.5 (transitions polish the seams that 7.5 creates); `emotional_arc` ↑ ≥ 0.2; `story_coherence` holds
- If fails, iterate xfade mappings (3 attempts) per `phase_7_flow.md` rollback

## Validation gates

1. **Logical:** all tests green; goldens manually approved
2. **General design:** advisor pass on the xfade filter-graph approach (ffmpeg filter complexity can rabbit-hole)
3. **Working:** real-API run on a fixture project produces a stitched mp4 where the operator visually confirms the transitions match the device picks
4. **Eval delta:** `visual_quality` ↑ ≥ 0.2; `emotional_arc` ↑ ≥ 0.2; `story_coherence` ≥ post-7.5

## Open questions

| Q | Default proposal | Decide when |
|---|---|---|
| Music bed in v1? | Punt to v1.1 | `phase_7_plan.md` decision #4 — locked |
| TTS narration | Defer to Phase 8+ | Locked |
| Default xfade duration if device doesn't specify | 0.5s | Step 3 — locked |
| What if a device has no good xfade equivalent (e.g. portal_door, obstruction_match)? | Fall back to `fade`; rely on the Kling-rendered clip itself for the visual transition | Step 1 |
| Audio handling (silence for now?) | Yes, silent until music bed lands in v1.1 | Locked |

## Rollback / failure mode

If 7.7 eval gate fails:
1. Are transitions actually applying? Inspect a stitched mp4 frame-by-frame — sometimes ffmpeg silently drops a filter.
2. Is duration too long, making the cut feel laggy? Reduce per-device durations.
3. If 3 iterations fail, revert to ffconcat hard cuts; the device picks become advisory-only and the eval lift comes from 7.4-7.5 alone. Document the regression.

## Memory pointers

- `phase_7_flow.md` — `cinematic_device.ffmpeg_xfade` shape (this sub-plan reads it)
- `project_quality_vision.md` — stitch polish as the perception-multiplier
- `project_business_model.md` — music bed deferred because v1 service stage doesn't need it for revenue

## What ships at end of 7.7 (= end of Phase 7)

- Story-aware pipeline with cinematic-device-aware transitions
- Three-tier judge stack live, calibrated, scored on every run
- Eval harness producing trend data
- Operator UI: Upload + Brief + Story Review + Generate-with-judges + Review-with-movie-judge + Eval Dashboard
- Cost ceiling: ~$0.50 typical / $0.92 worst-case per movie
- **Phase 7 done; ready to move to Phase 8 (SaaS readiness) or hold for service revenue first.**
