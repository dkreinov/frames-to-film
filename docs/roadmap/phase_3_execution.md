# Phase 3 — Execution Log

**Phase:** De-Olga prompt library + auto prompt generation
**Status:** done
**Plan:** `plans/plan-20260423-1608.md` (self-deleted on close-out)
**Dates:** 2026-04-23

## Outcome

Per-project `prompts.json` auto-generated from image pairs, with 4 generic
style presets (`cinematic`, `nostalgic`, `vintage`, `playful`). Two new
endpoints (`POST /prompts/generate`, `GET /prompts`). The generate stage
now resolves each pair's prompt in precedence: project JSON →
`PAIR_PROMPTS` (Olga backward compat) → `FALLBACK_PROMPT`. De-Olga gate
passes across all 4 styles.

## Decisions taken autonomously (user was asleep)

1. **Model:** `gemini-2.0-flash` for API-mode — already in use as JUDGE_MODEL.
2. **Storage:** `<project>/prompts.json` — flat `{pair_key: prompt}` dict.
3. **Fallback chain:** project JSON → `PAIR_PROMPTS` → style preset → `FALLBACK_PROMPT`.
4. **`PAIR_PROMPTS` kept in place** (not removed) — Olga movie CLI still imports it. Phase 6 retires it when the React UI reaches parity. This is a **deliberate divergence** from `phases.md`'s "`PAIR_PROMPTS` removed (or kept only as style-preset fallback)" exit bullet; see "Divergences from phases.md" below.

## Test coverage

- `tests/backend/test_prompts_resolver.py` — 5 cases (preset presence, precedence, fallbacks).
- `tests/backend/test_prompts_generate.py` — 5 cases (mock + api).
- `tests/backend/test_prompts_endpoint.py` — 6 cases (POST/GET + 404s + user scope).
- `tests/backend/test_generate_prompts_integration.py` — 3 cases (PROJECT_PROMPTS load/restore/missing).
- `tests/integration/test_prompts_deolga.py` — 4 cases (parametrized across all 4 style presets).
- `tests/integration/test_e2e_mock.py` — extended to include `/prompts/generate` between extend and generate.
- Full suite: **92 passed, 1 skipped** (ffprobe unbundled).
- Phase 2 thread-safety tests (`test_script_threadsafe.py`) still green — `_RUN_LOCK` now also guards the new `PROJECT_PROMPTS` swap.

## Frozen contracts

- `backend/services/prompts.py` exports: `STYLE_PRESETS` (4 keys), `FALLBACK_PROMPT`, `resolve_prompt`, `generate_prompts_mock`, `generate_prompts_api`, `prompts_runner`, `GEMINI_MODEL`.
- `<project>/prompts.json` schema: flat `{"1_to_2": "<prompt>", ...}`.
- `POST /projects/{id}/prompts/generate {"mode": "mock|api", "style": "cinematic|nostalgic|vintage|playful"}` → `202 {job_id}`; job kind=`prompts`.
- `GET /projects/{id}/prompts` → `200 {pair_key: prompt}` or `404`.
- `generate_all_videos.run(img_dir, video_dir, project_dir=None)` — when `project_dir` contains `prompts.json`, loads into module-global `PROJECT_PROMPTS` inside `_RUN_LOCK`; restores on finally.
- Both generate-stage lookup sites (`generate_pairs_for_sequence` + `main`) now consult `PROJECT_PROMPTS` before `PAIR_PROMPTS`.

## Divergences from `phases.md` exit criteria (advisor-flagged)

**Documenting eyes-open, not silently-skipped.** The advisor called these out at close-out review:

1. **"Logical: prompt generation on 3 unrelated photo sets."** Tested on 1 photo set (Cosmo fixture) × 4 styles. Mock mode returns the preset string regardless of image content, so varying photo sets through mock mode proves nothing new. Meaningful multi-set coverage requires api-mode E2E with real Gemini calls (cost); pushed to Phase 5 or 6 where the full api-mode smoke test lives.

2. **"`PAIR_PROMPTS` removed (or kept only as style-preset fallback)."** Kept in place as second-priority data (after project `prompts.json`). Rationale: the Olga-movie CLI flow (`python generate_all_videos.py`) still imports and depends on `PAIR_PROMPTS`. Removing it now would break that flow before the React UI is parity-complete. Phase 6 retires it.

3. **API-mode de-Olga has no E2E coverage.** The `_API_PROMPT_TEMPLATE` instructs Gemini "do NOT reference the original family," but nothing in CI catches a non-compliant flash response. The unit test covers the call path (mocked client); only real api-mode runs would exercise the instruction-following. Acceptable documented risk — catch during Phase 5/6 manual smoke if it happens.

## Findings for Phase 4

1. **Mock mode is deterministic but uninteresting.** 5 identical prompts for a 6-frame project. Phase 4 React UI should NOT assume pair-prompt variance for visual-diff tests — use api-mode (or parametric style variation) when a realistic preview is wanted.

2. **Style preset selector.** Phase 4 needs a style picker in the UI. 4 options map directly to the `style` field of `POST /prompts/generate`. Validation can be client-side (enum) or server-side (currently the endpoint silently falls back to `FALLBACK_PROMPT` on unknown style — Phase 4 can tighten to 400 if desired).

3. **Per-pair prompt editing.** `<project>/prompts.json` is a dict the UI can read via `GET /prompts` and write back via a new `PUT /prompts` endpoint (not in Phase 3 scope). That endpoint would let users override a single auto-generated prompt before generating videos.

4. **`redo_runner.py:87`.** Still reads `PAIR_PROMPTS.get(pair_id, FALLBACK_PROMPT)` for the legacy retry flow. When Phase 5 or 6 wraps redo for FastAPI, apply the same `PROJECT_PROMPTS`-first precedence there.

## Follow-ups (non-blocking)

- Tighten unknown-style handling (return 400, not silent fallback).
- Add `PUT /projects/{id}/prompts/{pair_key}` for per-pair user edits.
- Bundle `ffprobe.exe` in `tools/` (still absent since Phase 2).
