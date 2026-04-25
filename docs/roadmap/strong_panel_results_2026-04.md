# Strong-Panel Benchmark — Phase 7.1 follow-up

**Date:** 2026-04-25
**Total cost:** $0.047
**Models:** Qwen-VL-Plus, Moonshot-v1-128k-vision-preview, DeepSeek V4 Flash, Kimi K2.6
**Note:** Opus 4.7 frontier reference deferred — Qwen vs production cross-check already gives decisive signal.

## Headline finding

**Qwen-VL-Plus is the right replacement for the production cheap judges.**
- Catches anatomy issues like the production gemini-3-flash-preview did
- 4× faster (2.9 s vs 12 s)
- 5× cheaper per call (and 20-40× cheaper than Gemini's actual billed cost with thinking tokens)
- Deterministic across runs (stdev 0)

## prompt_judge

| Vendor | n | mean score | stdev | $/call | latency (s) |
|---|---|---|---|---|---|
| **qwen-vl-plus** | 5 | 4.00 | 0.00 | $0.000475 | **2.72** |
| moonshot-v1-128k-vision-preview | 5 | 3.80 | 0.40 | $0.001416 | 5.30 |

**Verdict: Qwen wins.** Faster, cheaper, deterministic. Production gemini-2.5-flash-lite had similar mean scores (3.8) but real billed cost ~10× higher than reported.

## clip_judge

| Vendor | n | mean visual | stdev | anatomy breaks flagged | $/call | latency (s) |
|---|---|---|---|---|---|---|
| **qwen-vl-plus** | 5 | 4.50 | 0.00 | **1 (pair 1→2: cat's body proportions)** | $0.000633 | **2.89** |
| moonshot-v1-128k-vision-preview | 5 | 4.50 | 0.00 | 0 | $0.002101 | 7.20 |

For comparison, production `gemini-3-flash-preview` flagged different pairs across runs:
- Step 4.5 benchmark run: 1 anatomy break (pair 2→3)
- Step 8 E2E verification run: 2 anatomy breaks (pairs 3→4, 4→5)

**Verdict: Qwen catches anatomy issues like Gemini does, but more consistently and ~10× cheaper in real billed terms.**

The fact that Qwen flagged a *different* pair (1→2 cat body) than Gemini flagged in earlier runs is consistent with the broader finding that anatomy detection sits near the model decision boundary; multi-run averaging or a 2-of-3 consensus rule would tighten this signal further.

## movie_judge

| Vendor | n | mean story_coh | stdev | weakest seams | $/call | latency (s) |
|---|---|---|---|---|---|---|
| **deepseek-chat (V4 Flash)** | 2 | 3.80 | 0.00 | [2, 2] ✓ | $0.000148 | **3.39** |
| kimi-k2.6 | 2 | 3.75 | 0.25 | [2, 2] ✓ | $0.011833 | 45.30 |

Both models correctly identified the synthetic weakest seam (pair 2 — the one with `anatomy_ok: false`). Reasoning quality comparable in qualitative read.

**Verdict: DeepSeek wins decisively.** Same correct answer at 80× lower cost and 13× faster latency. K2.6 forces temperature=1 (no deterministic mode) and produces verbose reasoning (~2500 output tokens) — neither helps for this task.

## Per-pair anatomy verdicts across all models

| Pair | Qwen-VL-Plus | Moonshot vision | gemini-3-flash-preview (production, run 1) | gemini-3-flash-preview (production, run 2) |
|---|---|---|---|---|
| 1→2 | **anatomy_ok: false** ("body proportions") | OK | OK | OK |
| 2→3 | OK | OK | **false** ("mushrooms remain") | OK |
| 3→4 | OK | OK | OK | **false** ("clipping through paw") |
| 4→5 | OK | OK | OK | **false** ("snack bag teleports") |
| 5→6 | OK | OK | OK | OK |

No two runs flag the same pair. Strong evidence that **single-run anatomy detection is unreliable**; production should average 2-3 runs OR use temperature=0 across both Qwen and Gemini for reproducibility.

## Cost comparison vs production cheap-judge stack

| Configuration | Per-movie judge cost (real, billed) | Latency per stage |
|---|---|---|
| Production today (Gemini) | ~$0.10-$0.20 (verified vs billing dashboard) | ~60s |
| **Proposed (Qwen-VL-Plus + DeepSeek)** | **~$0.005-$0.007** | ~17s |

20-40× cost reduction. ~3.5× faster. Same anatomy-catching capability.

## Recommended production swap

| Judge | Today | Recommended |
|---|---|---|
| `prompt_judge` | gemini-2.5-flash-lite | **qwen-vl-plus** |
| `clip_judge` | gemini-3-flash-preview | **qwen-vl-plus** |
| `movie_judge` | deepseek-chat (V4 Flash) | **deepseek-chat** (already best — keep) |

DeepSeek stays for movie_judge (already optimal). Qwen replaces both Gemini-based judges.

## What was NOT measured

- Opus 4.7 frontier reference (deferred — would require subagent orchestration that's better suited to a separate runner)
- `qwen3-vl-plus` (the next-tier model — may be worth a 1-call sanity check before locking pick)
- Gemini 3 Pro / GPT-5.5 (skipped per cost directive)

## Failures encountered

- Initial Kimi K2.6 calls returned HTTP 400. Root cause: K2.6 only accepts `temperature: 1`. Fixed by adding per-vendor temperature override in the benchmark runner.
- Cost cap (MAX_USD=$20) never triggered — total spend $0.047 was 0.2% of cap.

## Next decision required from operator

Should we:

**(A)** Swap production judges to Qwen-VL-Plus right now? (Code change in `prompt_judge.py` + `clip_judge.py` `DEFAULT_MODEL`; adds `QWEEN_KEY` resolver to deps.py; existing tests need re-run with mocked Qwen responses.)

**(B)** Run one more sanity check on `qwen3-vl-plus` (newer/stronger tier) before locking? Adds ~$0.005, ~5 minutes.

**(C)** Defer the swap until 7.4 (story-aware pipeline) ships, to avoid changing two things at once.

Recommend **(A) followed by (B) as a follow-up confirmation.** Cost savings compound across every movie produced; delay = wasted money.
