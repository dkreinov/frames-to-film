# Judge Model Benchmark — Phase 7.1 Step 4.5

**Date:** 2026-04-25
**Fixture:** wet-test cat-astronaut project (5 prompts, 5 mp4s)
**Total cost:** $0.019 (well under $0.50 cap)

## prompt_judge

| Model | n | mean score | stdev | $/call | latency (s) | errors |
|---|---|---|---|---|---|---|
| `gemini-2.5-flash-lite` | 10 | 3.8 | 0.75 | $0.000092 | 2.68 | 0 |
| `gemini-2.5-flash` | 10 | 2.5 | 1.02 | $0.000148 | 11.72 | 0 |
| `gemini-3-flash-preview` | 10 | 3.0 | 0.89 | $0.0 (preview) | 9.65 | 0 |

**Pick: `gemini-2.5-flash-lite`** — 4× faster than alternatives at the same cost; reasonable variance (stdev 0.75); mean score in the believable middle (cat-movie prompts were generic/cinematic, score ~3.8 makes sense). 2.5-flash is unexpectedly slow (~12 s) and gives harsher/noisier scores with no quality benefit. 3-flash-preview is currently free but locked to preview; not production-stable.

## clip_judge

| Model | n | mean visual | stdev | anatomy breaks | $/call | latency (s) | errors |
|---|---|---|---|---|---|---|---|
| `gemini-2.5-flash` | 5 | 4.8 | 0.24 | 0 | $0.000205 | 11.12 | 0 |
| `gemini-2.5-pro` | 5 | 4.5 | 0.77 | 0 | $0.002119 | 13.94 | 0 |
| `gemini-3-flash-preview` | 5 | 4.1 | 0.58 | **1 ✓** | $0.0 (preview) | 12.41 | 0 |

**Critical finding:** the wet-test 2→3 clip has a real anatomy issue (hands merging with package — confirmed in `wet_test_findings.md`). Only `gemini-3-flash-preview` flagged it. `gemini-2.5-flash` and `gemini-2.5-pro` both scored anatomy_ok=true on every clip — too lenient.

**Pick: `gemini-3-flash-preview`** — meaningful discrimination on anatomy. Cost $0 (preview tier) for now; when it goes GA the rate per `reference_model_prices_2026_04` is $0.50/$3.00 per M, ~$0.001/call, still cheap. **Fallback to `gemini-2.5-flash`** if 3-flash-preview becomes unavailable; document the regression in anatomy detection.

## movie_judge

| Model | n | mean story_coh | stdev | weakest seam picks | $/call | latency (s) | errors |
|---|---|---|---|---|---|---|---|
| `deepseek-chat` (V4 Flash) | 2 | 3.8 | 0.0 | [2, 2] | $0.000163 | 3.7 | 0 |
| `deepseek-reasoner` (R1, EOL Jul 2026) | 2 | 3.75 | 0.25 | [2, 2] | $0.002336 | 12.15 | 0 |

Both models correctly identified seam 2 (the anatomy break) as weakest. R1 is 14× more expensive, 3× slower, and gives effectively identical output quality on this task.

**Pick: `deepseek-chat` (V4 Flash)** — cheapest, fastest, picks the right weakest seam consistently. R1 is also retiring 2026-07-24, so committing to V4 Flash now avoids a forced migration later.

## Final picks (committed in code)

| Judge | Model | $/call | Notes |
|---|---|---|---|
| `prompt_judge` | `gemini-2.5-flash-lite` | $0.000092 | Speed + cost dominant |
| `clip_judge` | `gemini-3-flash-preview` | $0 → ~$0.001 GA | Catches anatomy issues 2.5-flash misses |
| `movie_judge` | `deepseek-chat` | $0.000163 | V4 Flash; R1 retiring Jul 2026 |

**Per-movie judge cost** (5 prompts + 5 clips + 1 movie call):
- prompt_judge: 5 × $0.000092 = $0.00046
- clip_judge: 5 × $0.001 (post-GA) = $0.005
- movie_judge: 1 × $0.000163 = $0.000163
- **Total: ~$0.005-0.006/movie** ← well under the $0.025 budget in `phase_7_overview.md`

## Methodology notes

- prompt_judge: each model ran 2× over 5 prompts (10 calls). Fixture = wet-test prompts.json paired with the source kling_test/{n}.jpg images.
- clip_judge: each model ran 1× over 5 mp4s (5 calls). Frames sampled at 0.2s, 2.5s, 4.5s.
- movie_judge: each model ran 2× on a synthetic per-clip judge JSON + story arc + brief (2 calls). Synthetic data deliberately included pair 2 with `anatomy_ok: false` to test weakest-seam ID.
- All cost figures from token usage × `_PRICE_PER_M_TOKENS` table in `backend/services/judges/base.py`.

## Re-run instructions

```
python tools/judge_benchmark.py
```

Quick mode (1 model per judge, ~$0.005):
```
python tools/judge_benchmark.py --quick
```

JSON output: `docs/roadmap/judge_model_benchmark_2026-04.json` for analysis tooling.
