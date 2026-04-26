# Stream A Cycle Execution Log — 2026-04-26

Combined close-out for **two consecutive autonomous cycles** that landed:
- Cycle 1: Phase 7.4 backend prep + Phase 7.5 cinematic devices catalog
- Cycle 2: CLI wrappers + orchestrator disk-load wiring + Phase 7.2 eval harness baseline

**Total commits:** 16 across the day. **Total cost:** $0.00 (all mock-mode). **Test delta:** 141 → 165 backend + integration tests passing (+24).

## Cycle 1 — 7.4 backend + 7.5 catalog (mid-day)

Plan file: `plans/plan-20260426-1150.md` (deleted on success)
Mode: autonomous, Opus, High thinking
Concurrent: Stream B running Sub-plan A + B (filesystem cleanup + path schema rename)

### What shipped

| Step | Commit | Files |
|---|---|---|
| 2 | `722a216` | `data/kling_prompt_rules.yaml` (research-backed; SCALE framework, 13 cam moves, 20 forbidden phrases) + `docs/research/kling_prompting_guide.md` (368 lines, 8 sections, 6 cited sources) |
| 3 | `fbb0c83` | 5 story arc YAMLs: life_montage, 3_act_heroic, travel_diary, event_recap, day_in_life |
| 4 | `6aba26e` | `data/cinematic_devices.yaml` (15 transitions w/ ffmpeg_xfade mapping) |
| 5 | `42b4255` | `tests/backend/test_story.py` (TDD red) |
| 6 | `2a45597` | `backend/services/story.py` (TDD green; vendor dispatch; qwen3-vl-plus default) |
| 7 | `0134178` | `tests/backend/test_prompt_writer.py` (TDD red) |
| 8 | `411be51` | `backend/services/prompt_writer.py` (TDD green; transition-aware) |
| 9 | `5563e8d` | `tests/backend/test_judges.py` extended for movie_judge story_arc + brief contract |
| 12 | `f2a7b48` | parallel_work_plan + CLAUDE.md "Active coordination points" |

Test delta: +15 (141 → 156).

## Cycle 2 — CLI + eval baseline (afternoon)

Plan file: `plans/plan-20260426-1230.md` (deleted on success)
Mode: autonomous, Opus, High thinking

### What shipped

| Step | Commit | Files |
|---|---|---|
| 2 | `aaf143c` | `tools/cli/run_story.py` + integration tests (mock-mode CLI wrapper for story.py) |
| 3 | `9f434c7` | `tools/cli/run_prompts.py` + integration tests (mock-mode CLI for prompt_writer.py) |
| 4 | `8eccc81` | TDD red — orchestrator must auto-load story.json + project.json brief from disk |
| 5 | `6498ae9` | TDD green — `_load_story_from_disk` + `_load_brief_from_project_json` in orchestrator |
| 6 | `01b67ba` | End-to-end mock smoke test (CLI chain → orchestrator disk load) |
| 7 | `4e71e60` | `fixtures/eval_set/01_cats/` (cats fixture metadata; 6 png photos in inputs/, gitignored) |
| 8 | `85bc84a` | `fixtures/eval_set/02_olga_slice/` (Olga life-montage 6-frame slice) |
| 9 | `1228f46` | `tests/integration/test_eval_runner.py` (TDD red) |
| 10 | `0c96cc7` | `tools/eval_runner.py` (TDD green; CSV schema locked) |
| 11 | `489ba04` | First `eval_runs.csv` row — mock baseline on both fixtures |
| 12 | `e39a17e` | `docs/roadmap/eval_baseline_2026-04.md` (CSV schema doc + ship/re-roll thresholds) |
| 13 | this commit | This execution log + Stream A status update + plan-file delete |

Test delta: +9 (156 → 165).

## Frozen contracts introduced (this whole day)

These survived both cycles and are now load-bearing across the codebase. Don't break without a version bump + migration:

- **`StoryDoc`** (Pydantic) in `backend/services/story.py` — output of write_story; persisted as `metadata/story.json`
- **`prompts/prompts.json` content shape** = `{pair_key: prompt_string}` (unchanged from existing pipeline; CLI run_prompts.py just populates it via the new prompt_writer)
- **`data/kling_prompt_rules.yaml`** schema — read by story.py + prompt_writer.py to build rubric
- **5 story arc YAMLs** in `data/story_arcs/{slug}.yaml` — schema with id/name/continuity_rule/pacing/music_tone/camera_language/transitions_preferred/story_writer_extra_instructions
- **`data/cinematic_devices.yaml`** — 15 transitions, each with id/name/description/applicable_arcs/required_image_hints/prompt_template/ffmpeg_xfade/duration_s/xfade_duration_s. Stream B's 7.7 will read this for stitch xfade dispatch.
- **`metadata/story.json`** — orchestrator auto-loads when run_post_stitch_judge called without explicit story_arc kwarg
- **brief in project.json** — `subject` + `tone` + `notes` keys (operator-facing)
- **`eval_runs.csv` schema** — 22 columns, append-only, locked in `tools/eval_runner.py`
- **`movie_judge.score_movie(story_arc=, brief=)`** — was already there from Phase 7.1; tests added this cycle codifying the contract

## Decisions made during execution

- **Defer `POST /projects/{id}/story` router.** Operator chose CLI-first; HTTP endpoint is for future GUI consumers. Backend services + CLI wrappers are sufficient for service-stage delivery now.
- **Mock-mode-first for eval baseline.** First real-API eval is operator's call; not run today.
- **Cats fixture before Olga.** Cats fixture has known ground truth (manual wet-test verdicts); Olga is the primary product target but more setup. Both shipped.
- **Combined exec log instead of per-sub-plan.** Two cycles + multiple sub-plans → one log. Reduces doc proliferation.
- **PNG → JPG conversion in eval_runner._seed_extended.** Cats fixture has PNGs from Gemini original output; generate.py globs *.jpg only. Cleaner to convert at seed time than to modify generate.py glob.
- **Movie_judge.py touched ONLY by tests this cycle.** Strict-additive policy honored throughout — Stream B's path-rename refactors landed cleanly.

## Concurrent Stream B activity

While Stream A ran these 16 commits, Stream B independently shipped:
- `49b9693` project_schema constants + ProjectMeta with TDD
- `cc3a6c1` STORAGE_ROOT_DIRNAME constant in deps + db
- `5f7dc08` services use schema constants
- `8b803ec` routers use schema constants
- `f504ed1` backend renamed to projects/ schema (Sub-plan B Step 12)
- (cleanup of repo-root files, Olga migration, _archive)

Net result: canonical `projects/{slug}/` layout in production. CLAUDE.md updated with hard rules for schema conformance. 141 backend tests + 90 frontend tests green when Stream B handed off.

## Per-cycle test deltas

| Phase | Backend tests | Note |
|---|---|---|
| Pre-cycle 1 | 141 | Stream B handoff state |
| Post-cycle 1 | 156 (+15) | story + prompt_writer + movie_judge contract |
| Post-cycle 2 | 165 (+9) | orchestrator disk-load + 4 integration tests for CLI/eval |

Plus 6 new integration tests in `tests/integration/` (CLI story, CLI prompts, e2e mock, eval runner ×4 — overlaps with backend count for some).

## Cost summary

- All 25 commits → $0.00 in real-API spend (mocked tests only)
- Eval baseline run → $0.00 (mock mode)
- Cumulative-day spend on this cycle's work: $0.00
- DeepSeek balance unchanged: $2.12
- Qwen free tier unchanged
- Kimi balance unchanged: $10

## Open follow-ups for next cycles

1. **First real-API eval run** (operator's call; ~$5-10) — produce real-data row in eval_runs.csv
2. **3 more eval fixtures** (travel_diary, event_recap, day_in_life) per `phase_7_subplan_2_plan.md` — round out the 5-fixture target
3. **Phase 7.3 calibration** with Opus-as-reference + cheap-tier rubric tightening — depends on having real-API eval rows
4. **Phase 7.4 router** (`POST /projects/{id}/story` HTTP endpoint) — defer until GUI is ready
5. **Phase 7.5 integration into prompts pipeline** — `prompt_writer.py` is built but not yet plumbed into the existing `prompts.py` flow. CLI run_prompts.py is the bridge for now; integrating into the stage runner is a separate decision (operator-controlled vs auto).
6. **Phase 7.5b** Wan 2.7 adapter — needs DashScope billing; Stream B option
7. **Phase 7.7** stitch xfade polish — Stream B's queue
8. **Phase 8** SaaS readiness — explicitly out of scope until paid-service stage validates demand

## Stream A status as of close

Free for next cycle. No locks held. movie_judge.py source untouched (only test additions). Schema-conformance hard-rules per CLAUDE.md respected (no hardcoded path strings introduced).

If Stream B is also free, the highest-leverage next move is **first real-API eval baseline** (cost ~$5-10, gives us real-data ground truth) OR **wire prompt_writer.py into the existing prompts stage runner** (so the auto pipeline uses transition-aware prompts by default, not just CLI).

## Plan files this cycle

- `plans/plan-20260426-1150.md` — deleted (Cycle 1 success)
- `plans/plan-20260426-1230.md` — deleted (Cycle 2 success, this commit)

Both confirmed deleted before this exec log was committed.
