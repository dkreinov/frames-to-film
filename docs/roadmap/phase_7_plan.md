# Phase 7 — Plan: Quality (story-aware pipeline + judge-driven eval)

**Status:** pending (this is the master phase plan; each sub-plan 7.1–7.7 will get its own `phase_7_subplan_N_plan.md` + `_execution.md`)
**Depends on:** Phase 6 close-out (parallelizable — design passes folded into 7.4 / 7.5)
**Origin docs:** `phase_7_overview.md`, `wet_test_findings.md`
**Memory:** `project_quality_vision.md`, `project_business_model.md`, `feedback_model_selection.md`, `reference_model_prices_2026_04.md`

## Phase goal

Turn a working pipeline (Phase 6) into a **good** pipeline that produces movies a paying client would accept. Specifically:

- A 6-photo upload → 25–30 s movie that has a **story**, not just 5 unrelated 5-s clips
- Quality measurable by an eval harness, not by vibes
- Re-rolls happen automatically on bad clips; operator only intervenes for craft cases
- Cost per movie ceiling: **~$0.92 worst case, ~$0.50 typical** (vs $0.42 today with no quality)
- Operator can deliver a finished client movie in **~10 minutes of attention** + ~5 minutes of generation wait

## Exit criteria (the gate to call Phase 7 done)

1. **Eval harness** runs on a fixed 5-project test set, producing scores per rubric dimension to `eval_runs.csv`. Trend visible across runs.
2. **AI ↔ human judge agreement ≥ 70%** on the calibration test set, measured at least once.
3. **All 5 story arcs** (life-montage, 3-act, travel, event, day-in-life) have working templates that pass eval at score ≥3.5/5 on story-coherence.
4. **Cinematic devices catalog** has ≥15 transitions, each with name, when-to-use, prompt template. Story writer picks from catalog only (no free-form transitions).
5. **Three-tier judge stack** runs end-to-end on every generation: prompt judge gate before Kling submit, clip judge after each clip with 1 re-roll budget, movie judge advisory after stitch.
6. **Operator UI** (modified Upload, new Story Review, modified Generate, modified Review) drives a full client movie in ≤10 min operator-time on a known-good fixture.
7. **CI green**: backend + frontend + Playwright suites pass for the new flows.
8. **No regressions**: Phase 6 mock-mode E2E still passes; all existing exit criteria hold.
9. **`/app-design`** + **`/frontend-design`** passes complete on the new UI surfaces (folded in here from Phase 6 remainder).

## Sub-plan list with dependencies

```
7.1 Judge prototypes ──────────┐
                               ├──→ 7.3 Calibration ──→ 7.4 Story arc ──→ 7.5 Cinematic devices
7.2 Eval harness ──────────────┘                                                   │
                                                                                   ├──→ 7.6 Web-sub path (optional/v1.1)
                                                                                   └──→ 7.7 Stitch polish
```

| # | Sub-plan | Days | Quality lift | Service-stage priority |
|---|---|---|---|---|
| **7.1** | Three-tier judge prototypes — `prompt_judge`, `clip_judge`, `movie_judge` services with minimal rubric prompts. Wired into pipeline behind a `JUDGES_ENABLED` flag (off in CI mock). ✓ **done** | 2 | indirect (enables 7.2) | **must-have** |
| **7.1.1** | Olga real-asset validation — Tests A/B/C audit auto-pipeline against operator's manually-finished 15-min reference movie. Gates investment in 7.2+. See `phase_7_subplan_1_1_plan.md`. | 0.5–1 | **decisive** (data drives every later sub-plan's priority) | **must-have BEFORE 7.2** |
| **7.2** | Eval harness — `fixtures/eval_set/` with 5 reference projects (diverse subjects, bring real photos), `eval_runner.py` that walks each through the pipeline and writes `eval_runs.csv`. Baseline run on current pipeline + Phase 7 judges only (no story changes yet). | 1-2 | indirect | **must-have** |
| **7.3** | AI ↔ human judge calibration — operator scores 5 reference movies on 4-dim rubric (story / continuity / visual / arc), AI judge scores same, compute agreement, iterate AI rubric prompt until agreement ≥70%. | 1-2 (incl. user time) | indirect | **must-have** |
| **7.4** | Story arc + brief input + story writer service + 5 arc templates. UI: arc-type radio + brief textarea on Upload; new Story Review screen. Backend: `services/story.py` with one call per movie + per-pair motion-intent output. | 2-3 | **HIGH** — biggest perceived lift | **must-have** |
| **7.5** | Cinematic devices catalog (≥15 entries, hand-curated from film grammar) + transition-aware prompt writer. Story writer picks transition per pair from catalog; prompt writer applies template. | 2-3 | **HIGH** — second lever | **must-have** |
| **7.5b** | Video generator A/B — Kling O3 vs Wan 2.7 i2v adapter, fixture re-renders, judge eval, decide default. See `phase_7_subplan_5b_plan.md`. | 2-3 | **HIGH for life-montage** (character continuity) | **must-have** before life-montage demos |
| **7.6** | Web-sub story path — composite-grid generator (2×3 PNG with corner labels, `services/grid_compose.py`) + Story Source toggle + paste-back UI. | 2 | low for service stage (operator already has API) | **optional / defer to v1.1** |
| **7.7** | Stitch polish — ffmpeg `xfade` cross-fade transitions per chosen device; optional music bed via Suno or ElevenLabs API; optional TTS narration. | 2 | medium (perceived polish) | **must-have for the cross-fades; music bed optional** |

**Total committed work (must-haves):** ~12-16 days
**With optional 7.6 + 7.7-music:** ~14-19 days

(7.5b adds 2-3 days; ships in parallel with 7.5/7.6/7.7 since it's a separate code path.)

## Five open decisions to lock before starting 7.4

These were surfaced in `phase_7_overview.md`. Need the user's call (or a "let's prototype and decide later" stance):

| # | Question | Default proposal | Notes |
|---|---|---|---|
| 1 | Default story-source | **API auto** (operator already pays APIs; web-sub is an edge case) | Reverses overview pick now that we know it's service stage |
| 2 | Re-roll budget | **1 retry per movie**, not per clip | Bounds worst-case cost at $0.92; operator can manually re-roll more if needed |
| 3 | Eval cadence | **Run on every sub-plan close**, plus on-demand during 7.4/7.5 prompt iteration | CI run is too expensive ($2.50/run × 100 PRs = $250); manual cadence is enough |
| 4 | Music bed in 7.7 | **Punt to v1.1** | Cross-fades alone are a real lift; music adds API plumbing + licensing concerns |
| 5 | Default story arc on Upload | **Life-montage** (Olga's actual use; first paying-client likely a similar family/timeline brief) | User can override per-project |

These five become the basis for the first sub-plan's input; defaults stand unless the user flips one.

## Operator UX changes (per sub-plan)

7.4 + 7.5 + 7.7 each touch the UI. Wireframes live in `phase_7_overview.md` § "Operator UX" (to be added). Summary:

- **Upload screen**: + arc-type radio, + brief textarea, + story-source toggle
- **Story Review** (new screen between Upload and Generate): editable arc paragraph + per-pair motion intents + transition picks
- **Generate screen**: + per-clip judge score chip + re-roll button per clip + cost meter
- **Review screen**: + movie-level judge scorecard + weakest-seam suggestion + targeted re-roll button
- **Eval Dashboard** (new admin/operator screen): run history, score trends, AI/human agreement metric, [Run new eval] / [Export CSV] / [Compare runs]

`/app-design` + `/frontend-design` passes happen on these surfaces during 7.4 / 7.5 work. Phase 6's remaining design-pass items are folded in here.

## Validation gates (per sub-plan, mirrors project convention)

Each sub-plan must pass before merge:

1. **Logical**: pytest + vitest green; new tests cover the new code paths.
2. **General design**: advisor pass on the architecture choice (services, contracts, data flow).
3. **App design** (only for sub-plans touching UI): `/app-design` pass.
4. **Frontend design** (only for UI sub-plans): `/frontend-design` pass.
5. **Working**: end-to-end test on the new flow runs successfully on a known fixture set.
6. **Eval delta** (from 7.4 onward): `eval_runs.csv` shows score motion in the expected direction. **No-ship if scores don't move up.**

## What is explicitly out of scope (Phase 8+)

- Auth / login / user accounts
- Stripe / billing / subscription tiers
- Multi-tenant isolation (single-operator app for Phase 7)
- Public marketing landing page
- Vercel / cloud deploy
- Mobile app
- Bulk/batch operator UI for >1 client at a time

These belong to Phase 8 once the paid-service stage validates demand.

## Memory pointers

- `~/.claude/projects/.../memory/project_quality_vision.md` — full architecture rationale
- `~/.claude/projects/.../memory/project_business_model.md` — three-stage business model + Phase 7 = service stage
- `~/.claude/projects/.../memory/feedback_model_selection.md` — old+cheap-first model rule
- `~/.claude/projects/.../memory/reference_model_prices_2026_04.md` — current pricing snapshot

## Next concrete step

User locks (or flips) the five open decisions above. Then `/plan` for sub-plan 7.1 (judge prototypes) since 7.1 + 7.2 + 7.3 are all "infrastructure" and don't need the decisions resolved yet. Decisions 1, 2, 5 only matter at 7.4. Decisions 3, 4 matter at eval cadence and 7.7 polish.

So unlocking 7.1 is **immediate** — no decisions blocking. Start there.
