# Parallel Work Plan — Two Claude Code Sessions

**Created:** 2026-04-26
**Goal:** ship Phase 7 sub-plans 7.2, 7.4, 7.5, 7.5b, 7.7 in parallel without git conflicts, without one stream blocking the other.

## Current state (where we start)

- Phase 7.1 ✓ done (judge stack)
- Phase 7.1.1 ✓ done (Olga real-asset validation, v2 source-aware judges shipped)
- 135 backend tests green
- Production judges: `qwen3-vl-plus` for prompt + clip; `deepseek-chat` for movie. ~$0.05/movie.
- Latest commit: `0084b3f` (v2 production judges)

**Open sub-plans:** 7.2 (eval harness), 7.3 (calibration), 7.4 (story arc), 7.5 (cinematic devices), 7.5b (Wan 2.7 A/B), 7.6 (web-sub story path, optional), 7.7 (stitch polish).

## Stream split

The split is **by file ownership**, not strictly by sub-plan, because some sub-plans touch both backend + frontend. Each stream owns its files until done; the other stream doesn't edit them.

### Stream A — Backend pipeline + eval (this session continues)

**Sub-plans:** 7.2, 7.4 backend, 7.5

**Files owned by A:**
- `backend/services/story.py` (new — 7.4)
- `backend/services/prompts.py` (modify — 7.4 story-conditioned prompts)
- `backend/routers/story.py` (new — 7.4 endpoint)
- `data/story_arcs/*.yaml` (new — 5 arc templates)
- `data/cinematic_devices.yaml` (new — 7.5 catalog ~15 transitions)
- `backend/services/prompt_writer.py` (new — 7.5 transition-aware)
- `backend/services/judges/movie_judge.py` (modify — accept story_arc + brief inputs)
- `tools/eval_runner.py` (new — 7.2)
- `fixtures/eval_set/` (new — 7.2 reference projects)
- `tests/backend/test_story.py` (new — 7.4)
- `tests/backend/test_prompt_writer.py` (new — 7.5)
- `tests/integration/test_eval_runner.py` (new — 7.2)

**Stream A first task:** 7.2 eval harness — lets us measure the lift of every later change.

### Stream B — Frontend + new backend services (new session)

**Sub-plans:** 7.4 frontend, 7.5b, 7.7

**Files owned by B:**
- `frontend/src/routes/UploadScreen.tsx` (modify — 7.4 brief + arc-type radio + story-source toggle)
- `frontend/src/routes/StoryReviewScreen.tsx` (new — 7.4)
- `frontend/src/routes/GenerateScreen.tsx` (modify — judge score chips + re-roll buttons)
- `frontend/src/routes/ReviewScreen.tsx` (modify — movie judge scorecard + weakest-seam suggestion)
- `frontend/src/routes/SettingsScreen.tsx` (modify — Qwen + DeepSeek key inputs)
- `frontend/src/api/*` (modify — new endpoint clients for `/story` etc.)
- `frontend/src/hooks/*` (modify — useStory hook)
- All Playwright tests (`tests/playwright/*`)
- All vitest tests (`frontend/src/**/__tests__/*`)
- `backend/services/wan_25.py` (new — 7.5b adapter)
- `backend/routers/wan_25.py` (if needed — 7.5b endpoint)
- `tests/backend/test_wan_25.py` (new — 7.5b mocked HTTP)
- `tests/backend/test_wan_25_real.py` (new — 7.5b slow_real)
- `backend/services/stitch.py` (modify — 7.7 ffmpeg xfade)
- `tests/backend/test_stitch.py` (modify — 7.7 golden-frame compare)

**Stream B first task:** 7.5b Wan 2.7 adapter — totally isolated new file, no conflicts with A. Mirror `kling_fal.py` pattern. Plus user wants character-continuity validation.

## Shared files (NEITHER stream edits without coordination)

These files are shared infrastructure. **Only one stream edits at a time. Coordinate via Slack/text/whatever before touching.**

- `backend/services/judges/clip_judge.py` (just shipped; only patch if v2 has bugs)
- `backend/services/judges/prompt_judge.py` (same)
- `backend/services/judges/orchestrator.py` (same)
- `backend/deps.py` (key resolvers — coordinate if adding new vendor)
- `backend/main.py` (router registration — coordinate if adding new routes)
- `docs/roadmap/phase_7_*.md` (plan docs — append-only, both can read)
- `docs/roadmap/phases.md` (status table — append-only)
- `pyproject.toml` / `requirements*.txt` (deps; coordinate if adding new package)
- `frontend/package.json` (same)
- This file (`parallel_work_plan.md`)

If both streams need to touch a shared file:
1. Whoever needs it first announces "taking shared file X"
2. Other stream waits or pivots to a different task
3. After commit + push, releaser announces "shared file X released"

## Sync protocol

**Both streams:** pull frequently. Push frequently. Don't sit on uncommitted work for more than ~30 min.

```
# Before starting work each cycle
git pull --rebase origin master

# After every meaningful unit of work (test passes, feature complete)
git add <your files only>
git commit -m "..."
git pull --rebase origin master
git push origin master
```

Conflict on rebase = pause, resolve, re-test, push. If resolution unclear, ping the human operator.

## Daily / per-cycle alignment

Each stream writes its progress here at the end of each work cycle:

### Stream A status (latest)

```
[2026-04-26 evening] In progress: ___
Last commit: ___
Next up: ___
Blocked on: none / waiting for B's API contract / etc.
```

### Stream B status (latest)

```
[2026-04-26] In progress: Sub-plan B — backend rename to canonical projects/ schema
            (plans/plan-B-20260426-1500.md, autonomous). Plan A complete.
Last commit: bfde24f (Sub-plan A done — schema doc + _template + Olga migrated + archive)
Next up: nothing queued after Sub-plan B; resume Stream B 7.7/7.5b/7.4-frontend after.
Blocked on: none.

🔒 SHARED-FILE LOCK ACTIVE (Sub-plan B in progress)
    Stream A: please PAUSE edits to these files until Sub-plan B completes:
      backend/deps.py
      backend/db.py
      backend/services/{generate,prompts,prepare,extend,stitch}.py
      backend/services/judges/orchestrator.py
      backend/routers/{videos,uploads,outputs,artifacts}.py
      tests/backend/* (most files; rename touches fixture paths)
      frontend/src/api/* + frontend/src/routes/* (path-string updates)
    Lock released by Sub-plan B's Step 12 commit ("backend renamed to projects/ schema").
```

(Each session updates only its own status row when it commits.)

## API contracts that both streams need

Stream A produces these. Stream B consumes them. **Lock the shapes early; don't change without notice.**

### `POST /projects/{id}/story` (7.4)

Request body:
```json
{
  "arc_type": "life-montage" | "3-act-heroic" | "travel-diary" | "event-recap" | "day-in-life",
  "brief": {
    "subject": "string",
    "tone": "string",
    "notes": "string"
  },
  "regenerate": false
}
```

Response:
```json
{
  "story": {
    "arc_paragraph": "string (3 paragraphs)",
    "pair_intents": [
      {
        "from": 1,
        "to": 2,
        "device": "age_match_cut",
        "intent": "one-sentence motion description"
      }
    ]
  },
  "model_used": "string",
  "cost_usd": 0.01
}
```

Persisted to `pipeline_runs/local/{user_id}/{project_id}/story.json`.

### `cinematic_device` catalog entry (7.5)

`data/cinematic_devices.yaml` schema:
```yaml
- id: age_match_cut
  name: "Age match cut"
  description: "Hold on facial feature, dissolve preserves identity"
  applicable_arcs: [life-montage, event-recap]
  prompt_template: |
    Open on close-up of {subject_feature} in image A.
    Hold for 1 second. Slow dissolve to image B preserving
    the same {subject_feature} centered in frame.
  ffmpeg_xfade: fade
  duration_s: 5
```

Stream B reads this in 7.7 to map device → ffmpeg flag.

### `Mode` value for video gen (7.5b)

If Stream B ships 7.5b adapter, add `VIDEO_GENERATOR=kling|wan` env var dispatch in `backend/services/generate.py`. **This is a shared file** — coordinate before editing. Recommend B writes the adapter standalone first; A integrates the dispatch in a separate small commit after coordination.

## First-cycle task assignments

### Stream A — start with 7.2 (eval harness)

1. Pick 5 reference projects for `fixtures/eval_set/`
   - Use existing Olga test data (clips 24, 30, 34, 36, 5, 15 are already validated)
   - Plus 2-3 fresh photos sets if available
2. Build `tools/eval_runner.py`
   - Walks each project: prompts → judges → mp4 outputs
   - Captures per-rubric scores into `eval_runs.csv`
   - Append-only schema, git-tracked
3. Run baseline: post-7.1.1 v2 production judges on the 5 fixtures
4. Commit + push
5. Move to 7.4 backend (story_writer service)

### Stream B — start with 7.5b (Wan 2.7 adapter)

1. Operator (you) registers DashScope at `https://bailian.console.alibabacloud.com/?region=ap-southeast-1` and tops up ~$5 if you want to A/B Wan 2.7. **Skip this stream's task if you'd rather not pay yet** — pivot Stream B to 7.7 (stitch polish) which costs $0.
2. If proceeding: build `backend/services/wan_25.py` mirroring `kling_fal.py`
3. Add `WAN_25_MODEL_ID = "wan2.7-i2v"`
4. Adapter has `generate_pair(image_a, image_b, prompt, key, duration=5, resolution="720p") -> bytes`
5. Mocked unit tests + slow_real smoke
6. Document in `phase_7_subplan_5b_execution.md`
7. Commit + push (NEW FILE only, no shared-file edits yet)
8. Move to 7.7 (stitch polish — also pure backend)

If Stream B doesn't want to pay for Wan A/B, swap order:
1. **7.7 first** (stitch polish — ffmpeg xfade by device id, $0 cost)
2. **7.4 frontend** (UploadScreen + StoryReviewScreen — wait for A's `/story` endpoint contract)

## Conflict resolution

**Git conflicts:** rebase, resolve in favor of the most recent committed change, re-test, push. If unsure, page the human operator and DON'T force-push.

**API contract conflicts:** if A changes the `/story` response shape after B already wrote consumer code, A is responsible for updating both ends. Don't break consumers without coordination.

**Test conflicts:** if both streams add tests with the same name (unlikely with file ownership in place), rename newer test to be unique.

**Shared-file overlap:** if both streams MUST edit a shared file in the same cycle, the second stream waits. The first stream announces "taking X", commits ASAP, pushes, announces "released X".

## Daily checkpoint rhythm

Every ~half-day or when a significant chunk lands:
1. Both streams pull
2. Both streams update their status block above
3. Operator (you) reviews progress, decides next priorities, may re-assign work between streams
4. Resume

## Bootstrap for the new session (Stream B)

Paste this into the second Claude Code window after `cd D:\Programming\olga_movie`:

```
You're Stream B in a parallel-work split. Read these in order:

1. docs/roadmap/parallel_work_plan.md  — your file ownership + protocol
2. docs/roadmap/phases.md              — current phase status
3. docs/roadmap/phase_7_plan.md        — Phase 7 master plan
4. docs/roadmap/phase_7_subplan_5b_plan.md  — your first task (Wan 2.7 adapter)
5. docs/roadmap/phase_7_subplan_7_plan.md   — your second task (stitch polish)
6. docs/roadmap/phase_7_subplan_4_plan.md   — your eventual frontend task
7. CLAUDE.md (if present)              — project conventions

Memory pointers:
- ~/.claude/projects/.../memory/MEMORY.md (auto-loaded)
- Key memories: project_quality_vision.md, project_business_model.md,
  feedback_model_selection.md

DO NOT edit files Stream A owns. See parallel_work_plan.md § "Stream split".

When ready, decide between:
(a) 7.5b Wan 2.7 adapter (requires user to register DashScope first)
(b) 7.7 stitch polish (no signup, pure ffmpeg work)

Then start. Update parallel_work_plan.md § "Stream B status" after each commit.
```

## Estimated parallel timeline

If both streams hit 4-6 hours of focused work per cycle:

| Cycle | Stream A | Stream B |
|---|---|---|
| 1 | 7.2 eval harness baseline | 7.7 stitch polish (or 7.5b if Wan key ready) |
| 2 | 7.4 backend (story service + arc templates) | 7.5b Wan adapter (or 7.7) |
| 3 | 7.5 cinematic devices catalog | 7.4 frontend (Upload + StoryReview) |
| 4 | 7.5 prompt-writer integration | 7.4 frontend (Generate + Review with judges) |
| 5 | Eval delta runs after each merge | 7.6 web-sub path (optional) |
| 6 | Buffer / fixes | Buffer / fixes |

**Estimated total: ~3-4 calendar days of focused parallel work** (vs ~7-8 days serial).

## What NOT to do

- Don't both rebase + force-push at the same time
- Don't edit a shared file without coordination
- Don't wait silently when blocked — say so in your status row
- Don't change committed API contracts without telling the other stream
- Don't skip tests — even on parallel work, every commit must keep tests green

## Hand-back to human (you)

The human operator's role:
- Decide which stream takes which sub-plan when ambiguous
- Resolve API-contract disputes
- Approve costly real-API runs
- Watch the wallet (Gemini bill audit happened — keep an eye)
- Decide when a sub-plan is done enough to move on

If a stream is genuinely stuck, escalate via this doc's status block + a one-line ping in chat.
