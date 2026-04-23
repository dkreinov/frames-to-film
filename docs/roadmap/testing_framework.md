# Testing framework

Every phase passes **four gates** before it can be marked `done`. Missing any gate = phase stays in `review` status.

## Gate 1 — Logical

Code-level correctness: the things a compiler/test runner can prove.

- Unit tests via `pytest` (backend) or `vitest` (frontend) where the unit is small enough to isolate
- Integration tests for any multi-script flow (e.g. prepare → generate → stitch in mock mode)
- Type checks: `python -m py_compile` at minimum; mypy if introduced
- No skipped tests without a referenced reason

Artifacts: test file paths listed in `phase_<N>_execution.md`, last pytest output captured.

## Gate 2 — General design

Architectural soundness: invariants, failure modes, blast radius, seams that later phases will need.

Runs via `advisor()` **before declaring the phase done**. Advisor sees the full conversation, including every file written. If advisor raises a structural concern that survives a reconcile call, address it before moving on.

Artifacts: summary of advisor findings + responses logged in `phase_<N>_execution.md`.

## Gate 3 — App design (UI phases only: Phase 4, Phase 6)

Visual and interaction quality. Two skills:

- `/app-design` — makes UIs genuinely beautiful (typography, color, motion, layout, atmosphere). Runs on each screen.
- `/frontend-design` — catches AI-slop aesthetics in React/Tailwind components.

Artifacts: screenshot gallery per screen + list of suggested fixes (addressed or logged).

## Gate 4 — Working

End-to-end reality check on real inputs. Three accepted forms:

- **Playwright E2E** — automated, preferred where stable. Uses `mock` generation mode.
- **Claude-in-Chrome manual drive** — for exploratory phases, captures screenshot + GIF evidence via `mcp__claude-in-chrome__gif_creator`.
- **CLI smoke test** — for backend-only phases (Phase 1, 2, 3, 5). Typically a scripted curl/python call that exercises the happy path.

Artifacts: test run log + any output files (movie, images, API responses) saved to `pipeline_runs/phase_<N>_validation/` and referenced in `_execution.md`.

## Per-phase gate matrix

| Phase | Logical | General design | App design | Working |
|---|---|---|---|---|
| 1 Watermark | ✔ pixel diff | ✔ advisor | — | ✔ 3 real images |
| 2 FastAPI + mock | ✔ pytest | ✔ advisor | — | ✔ curl E2E in mock |
| 3 Prompts | ✔ no-Olga-leak test | ✔ advisor | — | ✔ spot check |
| 4 React UI | ✔ Playwright mock | ✔ advisor | ✔ `/app-design` + `/frontend-design` | ✔ Claude-in-Chrome |
| 5 Web-mode | ✔ file size/dur diff | ✔ advisor | — | ✔ 5-photo real run |
| 6 Ship | ✔ full E2E in CI | ✔ advisor | ✔ final pass | ✔ GIF recording |

## Iteration-feedback mechanics

After finishing a phase, **before** marking the next phase as `in-progress`:

1. Write the new findings to the current phase's `_execution.md` under a `## Findings that affect later phases` section.
2. Open the next phase's `_plan.md` (if it doesn't exist yet, create via `/plan`).
3. Update it to absorb those findings. Record the diff in the next phase's `_plan.md` under a `## Revisions from Phase <N-1> findings` appendix.
4. Only then change task status and start execution.

## Fixtures for cheap E2E

- `tests/fixtures/segments/` — a curated subset of the existing 78 `kling_test/videos/seg_*.mp4` files, one per transition family
- `tests/fixtures/photos/` — small sample photo set (not Olga-specific) for non-regression runs
- `tests/fixtures/watermarked.png` — a known Gemini-watermarked image for Phase 1 pixel-diff test
