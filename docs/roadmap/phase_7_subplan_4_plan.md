# Phase 7 — Sub-Plan 4: Story arc + brief input + story writer

**Status:** pending
**Size:** 2-3 days
**Depends on:** 7.3 (calibrated judges so we can prove the lift)
**Unblocks:** 7.5 (cinematic devices), 7.6 (web-sub path), 7.7 (stitch polish)
**Quality lift:** **HIGH** — biggest single lever in Phase 7

## Goal

Replace the current per-pair-only prompt generation with a **story-aware** pipeline. Add a story-level call (1 per movie) that sees all 6 photos + a user-provided brief, returns a structured story (arc paragraph + per-pair motion intents + camera hints + continuity rules). Per-pair prompt writing becomes story-conditioned: each prompt knows the global arc, its position in the timeline, and the desired transition.

UI surface: brief + arc-type input on Upload, new Story Review screen between Upload and Generate.

## Inputs / outputs

**Inputs**
- Calibrated judges from 7.3
- 5 arc templates (life-montage, 3-act-heroic, travel-diary, event-recap, day-in-life) — to be authored in this sub-plan
- Operator's brief (subject, tone, notes)

**Outputs**
- `backend/services/story.py` — story-writer service
- `data/story_arcs/{arc_type}.yaml` — 5 arc templates
- `pipeline_runs/.../run.json` extended with `story_arc_type`, `brief`, `story` (per `phase_7_flow.md` shape)
- New API endpoint `POST /projects/{id}/story` (returns story; idempotent if already exists)
- Modified Upload screen: arc-type radio + brief textarea + story-source toggle
- New Story Review screen: editable arc paragraph + per-pair motion intents + (placeholder for transition picks from 7.5)
- Modified prompt-writer to consume `story.pair_intents` instead of generating from-scratch per pair
- Eval gate: `story_coherence` median across 5 fixtures rises by **≥ 0.5** vs 7.2 baseline

## Step list

### 1. Author the 5 arc templates
- `data/story_arcs/life_montage.yaml`:
  - continuity_rule: "same person aging across years; preserve identity (eyes, smile, body type)"
  - pacing: slow, contemplative
  - music_tone: nostalgic, swell at milestones
  - camera_language: soft fades, gentle pans, slow zooms
  - transitions_preferred: [age_match_cut, cross_dissolve, photo_frame, iris_pinhole]
  - story_writer_extra_instructions: "Identify life-stage moments..."
- Similar files for 3-act-heroic, travel-diary, event-recap, day-in-life
- Each template = ~30-50 lines YAML

### 2. `services/story.py` — story-writer
- **Model:** Gemini 2.5 Pro (per memory rule: top tier for the 1 hardest call)
- **Inputs:** `(images: list[Path], brief: dict, arc_template: dict) → story_dict`
- **Output shape** (matches `phase_7_flow.md`):
  ```json
  {
    "arc_paragraph": "...",
    "pair_intents": [
      {"from": 1, "to": 2, "device": "age_match_cut", "intent": "..."},
      ...
    ]
  }
  ```
- Note: `device` is empty/null until 7.5 ships; story writer just suggests free-form "transition idea" string for now
- Image input: stack all 6 as multipart in a single Gemini call (Gemini 2.5 Pro supports this natively)
- Prompt construction: combines arc_template + brief + image content
- Tests: 3 mock cases per arc type (coherent → score 4-5, vague → 2-3, contradicting brief → 1-2)

### 3. Extend `run.json` schema
- Add `story_arc_type` and `brief` fields (top-level)
- Add `story` field with the story_dict
- Migrations: existing runs without these fields stay valid (treat as null/legacy)

### 4. New API endpoint
- `POST /projects/{id}/story` with body `{arc_type, brief}` → returns story_dict
- Idempotent: re-call returns existing story unless `regenerate=true` flag passed
- Cached on disk in `pipeline_runs/.../story.json`

### 5. Modify prompt-writer to consume story
- `backend/services/prompts.py` (or wherever per-pair prompts are generated)
- Old behaviour: for each pair, ask Gemini to describe motion between A and B
- New behaviour: for each pair, ask Gemini to write a Kling prompt that **executes** `story.pair_intents[i].intent` in the style of `arc_template.camera_language`, given image A and image B
- Cleaner prompts, story-grounded

### 6. UI: modify Upload screen
- Add: arc-type radio (5 options, life-montage default per phase_7_plan.md decision #5)
- Add: brief textarea (subject, tone, notes — see Phase 7 wireframe)
- Add: story-source toggle (API auto / Paste from sub) — per phase_7_plan.md decision #1, default API
- (7.6 implements the paste flow; this sub-plan adds the toggle UI scaffold)

### 7. UI: new Story Review screen
- Route: `/project/:id/story-review`
- Shows: editable arc paragraph + per-pair motion intents in a grid
- Buttons: [Regenerate], [Edit story], [Looks good →]
- Story score preview at the bottom (uses `prompt_judge` running on the proposed prompts)
- (Transition pills come in 7.5)

### 8. Wire the new screen into the wizard nav
- Upload → Story Review → Generate → Review (was Upload → Prepare → Generate → Review)
- Update navigation logic; add tests for the new flow

### 9. Tests
- Backend: unit tests for `story.py` with mocked Gemini responses (5 arc types × 3 cases each)
- Backend: API endpoint test `POST /projects/{id}/story` returns correct shape, idempotent
- Frontend: vitest for Upload screen new fields + Story Review screen rendering
- Playwright: full flow Upload → Story Review → Generate (in mock mode)

### 10. Eval gate run
- After merge candidate, run `tools/eval_runner.py --label "post-7.4"`
- Target: `story_coherence` median ↑ by ≥0.5 vs 7.2 baseline
- If fails → iterate prompts (story_writer rubric, arc templates) per `phase_7_flow.md` rollback plan

### 11. `/app-design` + `/frontend-design` passes
- Run `/app-design` on Upload + Story Review screens (Phase 6 remainder folded in here)
- Run `/frontend-design` once both screens are stable

## Validation gates

1. **Logical:** all unit + integration tests green; one real-API smoke per arc type
2. **General design:** advisor pass — story-writer contracts + UI flow
3. **App design:** `/app-design` pass on Upload + Story Review
4. **Frontend design:** `/frontend-design` pass
5. **Working:** end-to-end real-API run on a fixture project produces a story.json + story-aware prompts
6. **Eval delta:** `story_coherence` ↑ ≥ 0.5 vs baseline; no other dim regresses by >0.3

## Open questions

| Q | Default proposal | Decide when |
|---|---|---|
| Default story-source (API vs web-paste) | API auto | `phase_7_plan.md` decision #1 |
| Default arc on Upload | life-montage | `phase_7_plan.md` decision #5 |
| Brief field shape — free-form text or structured? | Structured (subject, tone, notes) | Step 6 — locked here |
| Can operator skip Story Review? | No — always show, even if auto-generated; one click to advance | Step 7 — locked here |
| Story regeneration cost limit | 3 free regens per project; 4th onward shows cost warning | Step 4 |

## Rollback / failure mode

If 7.4 ships but eval gate fails (`story_coherence` doesn't move):
1. Iterate on the story-writer rubric prompt (3 attempts)
2. If still flat, switch story model to Gemini 3 Pro per memory rule (3-4× cost, but if it works ship it)
3. If still flat, the arc_template format is wrong — re-design templates with operator review
4. If still flat after that, the assumption "story-aware prompts lift quality" is wrong — fall back to a simpler approach (per-pair prompts with shared style preamble)

Eval is the arbiter, not vibes.

## Memory pointers

- `project_quality_vision.md` — story arc types + camera language hints
- `project_business_model.md` — operator UX priorities (density > polish, judge scores visible)
- `phase_7_flow.md` — `pair_intents` contract (locked after this sub-plan)
- `feedback_model_selection.md` — old+cheap default; only upgrade story model if eval forces it
