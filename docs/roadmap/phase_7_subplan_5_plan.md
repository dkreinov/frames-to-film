# Phase 7 — Sub-Plan 5: Cinematic devices catalog + transition-aware prompt writer

**Status:** pending
**Size:** 2-3 days
**Depends on:** 7.4 (story writer produces `pair_intents`; prompt writer reads them)
**Unblocks:** 7.7 (stitch maps device → ffmpeg xfade flag)
**Quality lift:** **HIGH** — second-largest lever after story arc

## Goal

Curate a hand-picked catalog of ~15 cinematic transitions (match cuts, iris, portal, age-match-cut, dolly-zoom, whip-pan, photo-frame, etc.). Story writer (7.4) picks one transition per pair from the catalog. Prompt writer applies that transition's template to produce a Kling-ready prompt. Transition picks become visible to the operator on the Story Review screen.

## Inputs / outputs

**Inputs**
- Story writer from 7.4 (extended to pick devices)
- Working judges from 7.1-7.3 (to score the lift)
- Film grammar references (StudioBinder, Walter Murch, etc.)

**Outputs**
- `data/cinematic_devices.yaml` with ≥ 15 entries (shape per `phase_7_flow.md`)
- `backend/services/prompt_writer.py` — transition-aware: takes `(pair_a, pair_b, story.pair_intents[i], device_template)` → Kling prompt
- Story writer extended: chooses `device_id` from the catalog when generating `pair_intents`
- UI: Story Review screen shows the chosen device per pair as a pill / tag with description hover
- Eval gate: `visual_quality` median ↑ ≥ 0.3 vs post-7.4; `story_coherence` holds or rises; re-roll rate ≤ 20%

## Step list

### 1. Curate the 15 starter devices
Hand-build the YAML catalog from film grammar. Suggested starter list:

| id | name | best for arcs |
|---|---|---|
| age_match_cut | Age match cut | life-montage |
| cross_dissolve | Cross dissolve | all (default fallback) |
| photo_frame | Photo-frame match cut | life-montage, event-recap |
| iris_in | Iris-in transition | nostalgic, life-montage |
| iris_pinhole | Pinhole zoom into B | reveal, place change |
| portal_door | Portal / door reveal | place change, fantasy |
| obstruction_match | Camera obstruction match cut | comedic, action |
| whip_pan | Whip pan | high energy, NOT life-montage |
| match_cut_shape | Shape match cut | abstract, transition |
| match_cut_action | Match-on-action | day-in-life |
| dolly_zoom | Dolly-zoom (vertigo) | revelation moment |
| smash_cut | Smash cut to silence/action | event-recap peaks |
| graphic_match | Graphic / colour match | abstract, art |
| fade_to_black | Fade to/from black | start/end of arc |
| time_card | Time card insert (text "10 years later") | life-montage |

Each entry follows the `phase_7_flow.md § cinematic_device` schema. Includes: id, name, description, applicable_arcs, required_image_hints, prompt_template (with placeholders), ffmpeg_xfade flag, default duration.

### 2. Extend story writer to pick devices
- `services/story.py` updated: prompt now sees the catalog; for each pair, choose the device that best fits the arc + image content
- Constraint: choose only from catalog (no free-form transitions)
- Output: `pair_intents[i].device` is a valid catalog `id`
- Tests: validate that all 5 arc types pick device ids that exist in catalog

### 3. `services/prompt_writer.py` — transition-aware
- Reads `(image_a, image_b, story.pair_intents[i], device_template)`
- Resolves `prompt_template` placeholders with image-specific content (e.g. `{subject_feature}` → "her brown eyes")
- Returns a Kling-ready prompt string
- Tests: 15 cases, one per device, asserting placeholder resolution + plausible output shape

### 4. UI: device pills on Story Review
- Each `pair_intents[i]` row shows a pill: device name + tooltip with description
- (Optional, defer to v1.1: dropdown to override the device choice)

### 5. Re-run prompt-image alignment via `prompt_judge`
- Story Review preview score now includes per-pair prompt judge output
- Operator sees if any pair's prompt is misaligned before generating

### 6. Tests
- Catalog validity: all entries parse, all `id`s unique, all `applicable_arcs` reference real arc types
- Story writer: device picks are catalog-valid
- Prompt writer: 15 placeholder resolutions
- Frontend: device pill renders + tooltip shows
- Playwright: full flow Upload → Story Review (with devices) → Generate

### 7. Eval gate run
- `tools/eval_runner.py --label "post-7.5"`
- Target: `visual_quality` median ↑ ≥ 0.3 vs post-7.4; `story_coherence` holds; re-roll rate ≤ 20%
- If fails: iterate prompt templates in catalog (3 attempts) per `phase_7_flow.md` rollback

## Validation gates

1. **Logical:** all tests green; eval run completes without crash
2. **General design:** advisor pass — confirm catalog format is operator-extensible (adding a 16th device is a YAML edit, not a code change)
3. **App design:** `/app-design` pass on the device-pill addition to Story Review
4. **Working:** end-to-end real-API run produces clips that show the chosen transition (visually verifiable on at least 3 pairs)
5. **Eval delta:** `visual_quality` ↑ ≥ 0.3, `story_coherence` ≥ post-7.4, re-roll rate ≤ 20%

## Open questions

| Q | Default proposal | Decide when |
|---|---|---|
| Catalog scope (15 vs 25) | 15 baseline; expand only if eval shows demand | Step 1 — locked |
| Operator override of device choice | Defer to v1.1 (auto-pick is the bet for 7.5) | Step 4 |
| Conflicts between two adjacent transitions (e.g. two whip-pans in a row) | Story writer constraint: avoid same device twice in a row | Step 2 |
| New device authoring tool | YAML edit + reload; no UI tool needed for service stage | Locked |

## Rollback / failure mode

If 7.5 eval gate fails:
1. Inspect: are devices being picked sensibly per arc? Re-tune story-writer prompt about device selection.
2. Are prompt templates producing Kling-friendly output? Tighten templates.
3. If 3 iterations fail, fall back to a simpler 5-device catalog (cross_dissolve, age_match_cut, photo_frame, iris_in, fade_to_black) and re-run.

## Memory pointers

- `project_quality_vision.md` — cinematic devices section + film-grammar examples
- `phase_7_flow.md` — `cinematic_device` shape (locked here)
- `feedback_model_selection.md` — applies if we consider upgrading prompt writer model
