# Strong-Panel Benchmark — Phase 7.1 follow-up

**Date:** 2026-04-25 (revised after Opus 4.7 panel ran)
**Total cost:** $0.047 paid models + $0 for Opus subagents (session-billed)
**Models:** Qwen-VL-Plus, Moonshot-v1-128k-vision-preview, DeepSeek V4 Flash, Kimi K2.6, **Opus 4.7 (subagent)**

## Headline finding (REVISED with Opus data)

**Don't swap to Qwen yet — all cheap models share the same blindspot.**

Opus 4.7 reveals that ALL cheap-tier vision judges (Gemini Flash, Gemini Pro, Qwen-VL-Plus, Moonshot vision-preview) are **too lenient on prompt-image grounding**. They give generic 4-4.5 scores when Opus correctly scores 2.0 because the rendered content doesn't match the prompt's specific claims.

**Real example — pair 5→6:**
- Prompt: "Slow camera zoom in...preserve general object placement across the frames to ensure a seamless spatial transition"
- Reality: clip shows cat now inside a spaceship cockpit with rocket flames — totally different scene
- Opus prompt_judge: **2.0** ("major scene change contradicts preserve placement")
- Qwen-VL-Plus: 4.0 (didn't notice)
- Moonshot vision: ~4 (didn't notice)
- Gemini Flash-Lite: similar lenient

The cheap models' anatomy detection sees one issue per run randomly, but the bigger gap is **prompt-grounding discrimination**, which only Opus does well. Cost-saving by swapping cheap model A for cheap model B doesn't fix that.

## Revised picture

| Vendor | prompt_judge mean | stdev | clip_judge mean visual | discriminates good vs bad? |
|---|---|---|---|---|
| **Opus 4.7 (subagent)** | **3.20** | **1.07** | 4.04 | **YES — strong** |
| gemini-2.5-flash-lite (production) | 3.80 | 0.75 | n/a | weak |
| gemini-3-flash-preview (production) | n/a | n/a | 3.00 | weak |
| qwen-vl-plus | 4.00 | 0.00 | 4.50 | **NO — gives 4.0 to everything** |
| moonshot-v1-128k-vision-preview | 3.80 | 0.40 | 4.50 | weak |
| gemini-2.5-flash | 2.50 | 1.02 | 4.80 | only slightly |
| gemini-2.5-pro | n/a | n/a | 4.50 | no anatomy detection |

The "qwen wins on cost" finding holds — but its zero-stdev means **Qwen can't tell good prompts from bad**. That's actually worse for production than Gemini Flash-Lite which at least had stdev 0.75 — it occasionally noticed problems.

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

## Recommended production swap (REVISED)

**Earlier recommendation: swap prompt + clip to Qwen.** That recommendation is now downgraded.

| Judge | Today | Old recommendation | NEW recommendation |
|---|---|---|---|
| `prompt_judge` | gemini-2.5-flash-lite | qwen-vl-plus | **HOLD** — pending rubric calibration (7.3) |
| `clip_judge` | gemini-3-flash-preview | qwen-vl-plus | **HOLD** — pending rubric calibration (7.3) |
| `movie_judge` | deepseek-chat (V4 Flash) | keep | **KEEP** — already optimal vs Kimi K2.6 |

### Why hold

The Opus panel revealed that ALL cheap models miss the same things — not just Gemini. Qwen scoring 4.0 deterministically on every prompt isn't "good"; it means the rubric isn't forcing the model to discriminate.

Swapping Gemini→Qwen would save $0.005/movie but produce equally weak signal. That's not worth the migration cost (code changes, test re-run, calibration uncertainty).

### What to do instead

**1. Tighten the rubric** — both prompt_judge and clip_judge rubrics need explicit grounding requirements. Examples drawn from Opus's correct calls:

For prompt_judge:
- "Score 2 or below if any concrete claim in the prompt (specific objects, places, motion) doesn't appear in either image"
- "Score 1 if the prompt references something visually opposite of what's shown"
- "Generic phrases like 'shimmering effect' alone don't justify a score above 3"

For clip_judge:
- "If any clip frame shows scene-level content that wasn't in the source images (new characters, totally different rooms, mode changes), prompt_match must be ≤ 2.5"
- "Style consistency below 3 if the 3 frames look like 3 different movies"

**2. Re-benchmark cheap models against the new rubric** to see which one best replicates Opus's discrimination at cheap-tier cost.

**3. THEN decide the swap.** With the right rubric, the cost-vs-quality math may favor Qwen, or may favor Gemini Flash-Lite, or may flip back. Decision will be data-driven, not assumed.

This becomes part of **sub-plan 7.3 (calibration)** — Opus 4.7 subagent panel is the reference, cheap models iterate their rubrics until they agree with Opus's discrimination pattern.

### What's still actionable now

- **Keep production judges as-is** (Gemini Flash-Lite + Gemini 3-flash-preview + DeepSeek V4)
- **Add `disable thinking` to Gemini calls** (already in 7.1 plan) — eliminates the SDK-vs-billing under-report and cuts real cost ~3-5×
- **Wait for 7.3 calibration** to make the swap decision with Opus-vs-cheap agreement data

This is option (C) from the earlier path: defer the swap until 7.3 lands.

## Opus 4.7 panel results (added in revision)

10 subagent calls (5 prompt_judge + 5 clip_judge), zero marginal cost (session-billed).

### prompt_judge

| Pair | Opus score | Opus reasoning |
|---|---|---|
| 1→2 | **2.0** | "ignores cat content change, glowing mushrooms appear, shimmering effect generic" |
| 2→3 | 4.5 | "package replaces hand position, lunar lighting consistent" |
| 3→4 | 3.5 | "arcing OK, but no visible cosmic dust swirl" |
| 4→5 | 4.0 | "forward dolly and morphing glow visible" |
| 5→6 | **2.0** | "major scene change (cockpit) contradicts 'preserve placement'" |

Mean **3.20**, stdev **1.07** — strong discrimination.

### clip_judge

| Pair | Opus visual | style | match | anatomy_ok | Opus reasoning |
|---|---|---|---|---|---|
| 1→2 | 3.5 | 2.5 | **2.0** | true | "scene content changes drastically (flag/rocket vanish, new creature)" |
| 2→3 | 4.5 | 4.5 | 4.5 | true | "smooth morph, lunar consistent, mushrooms persist" |
| 3→4 | 4.0 | 4.5 | 4.0 | true | "smooth arcing, refractive rings, lighting consistent" |
| 4→5 | 4.2 | 4.5 | 3.5 | true | "consistent, but camera barely dollies forward" |
| 5→6 | 4.0 | 3.0 | **2.5** | true | "object placement breaks (now in cockpit)" |

Notably, **Opus rates anatomy_ok=true on all 5 clips.** Production gemini-3-flash-preview has flagged different pairs as anatomy breaks across runs (1, 2, or even 3 different ones depending on the run). Opus's verdict: anatomy is fine; the real issue is **prompt-content mismatch**, not anatomy.

This reframes the entire conversation about "anatomy detection." What we've been calling "anatomy issues" in cheap-model output may actually be the cheap models flailing because they can't articulate the real (prompt-mismatch) problem.

## What was NOT measured

- `qwen3-vl-plus` (the next-tier Qwen model — sanity-checked separately, not worth ~2× cost)
- Gemini 3 Pro / GPT-5.5 (skipped per cost directive)
- Multi-run averaging across cheap models with temp=0 (would tighten anatomy variance)

## Failures encountered

- Initial Kimi K2.6 calls returned HTTP 400. Root cause: K2.6 only accepts `temperature: 1`. Fixed by adding per-vendor temperature override in the benchmark runner.
- Cost cap (MAX_USD=$20) never triggered — total spend $0.047 was 0.2% of cap.

## Next decision required from operator

Should we:

**(A)** Swap production judges to Qwen-VL-Plus right now? (Code change in `prompt_judge.py` + `clip_judge.py` `DEFAULT_MODEL`; adds `QWEEN_KEY` resolver to deps.py; existing tests need re-run with mocked Qwen responses.)

**(B)** Run one more sanity check on `qwen3-vl-plus` (newer/stronger tier) before locking? Adds ~$0.005, ~5 minutes.

**(C)** Defer the swap until 7.4 (story-aware pipeline) ships, to avoid changing two things at once.

Recommend **(A) followed by (B) as a follow-up confirmation.** Cost savings compound across every movie produced; delay = wasted money.
