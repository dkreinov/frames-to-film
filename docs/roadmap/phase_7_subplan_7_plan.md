# Phase 7 — Sub-Plan 7: Stitch polish

**Status:** ⚠️ REVISED — original ffmpeg xfade premise was wrong (see note below)
**Size:** TBD after re-scoping
**Depends on:** 7.5 (cinematic devices catalog), 7.4 (story.json with pair_intents)

---

## ⚠️ Design correction (2026-04-26)

The original plan assumed ffmpeg xfade should be applied **between Kling clips** at stitch time.
This is incorrect.

**How the pipeline actually works:**

Each Kling clip is generated **first-frame → last-frame** (image A → image B). The cinematic
device (age_match_cut, cross_dissolve, whip_pan, etc.) is expressed via the **prompt template**
written by `prompt_writer.py` — Kling renders the motion/transition *inside* the clip itself.

When you concat clip(A→B) then clip(B→C):
- Clip A→B ends on image B
- Clip B→C starts on image B
- The seam is already seamless — both clips meet at the same frame
- Adding ffmpeg xfade on top blends the *landing* of one clip with the *launch* of the next,
  creating a double-transition artifact that looks worse, not better

**The `ffmpeg_xfade` field in `cinematic_devices.yaml`** was documented as metadata but
should not drive post-processing. The visual transition is the Kling clip content itself.

**Conclusion:** plain stream-copy concat (`concat_videos.run`) is correct. No ffmpeg
filter_complex needed at stitch time.

---

## Revised goal

Polish the stitch seam quality and output packaging without adding ffmpeg transitions on top
of Kling-rendered motion. Candidate work items (operator decides priority):

### A. Seam inspection + trim (optional)
Both clips start/end at the same source image. Depending on Kling's output, there may be a
brief freeze-frame at the seam (last frame of clip i = first frame of clip i+1). If visible,
trim 1-2 frames from clip ends before concat.

How to diagnose: ffprobe first/last frames of adjacent clips; compare pixel hash.

### B. Music bed (deferred to v1.1)
- `services/music.py` calls ElevenLabs or Suno
- Sized to movie length + arc tone
- Mixed in at stitch time
- Cost: ~$0.05/movie
- **Status:** defer per `phase_7_plan.md` decision #4

### C. TTS narration (deferred to Phase 8+)
Not needed for v1 service stage.

### D. Eval gate run
- `tools/eval_runner.py --label "post-7.7"` once eval runner ships (Stream A Step 10)
- Baseline already established by Stream A; 7.7 delta expected to be ~0 (correct,
  since stitch polish has no effect without music bed or seam trim)

---

## What stitch.py does today (correct)

`backend/services/stitch.py` → calls `concat_videos.run()` (stream-copy concat, no re-encode).
Output: `final/full_movie.mp4`. This is the right behavior. No changes needed unless seam
trimming (item A) is prioritized.

---

## What ships at end of Phase 7

- Story-aware pipeline: story arc → cinematic device per pair → Kling renders transitions
- Three-tier judge stack live and scored on every run
- Eval harness producing trend data (Stream A)
- Operator UI: Upload + Brief + Story Review + Generate-with-judges + Review-with-movie-judge
- Cost ceiling: ~$0.50 typical / $0.92 worst-case per movie
- **Phase 7 done; ready for Phase 8 (SaaS) or hold for service revenue first**
