# Phase 7 — Sub-Plan 6: Web-sub story upload path (composite grid + paste)

**Status:** pending — **OPTIONAL / can defer to v1.1**
**Size:** 2 days
**Depends on:** 7.4 (story writer + UI scaffolding for source toggle)
**Quality lift:** low (UX for sub users); cost saving for sub users only

## Why this is optional in service stage

In the paid-service stage, the operator already pays APIs out of revenue ($0.01 per movie). Saving that $0.01 by routing the story step through the user's Gemini/ChatGPT subscription is irrelevant vs the $50+ revenue per movie. **Demote to v1.1 unless the API path proves unreliable.**

This plan exists for completeness. Build only if:
1. API story-writer becomes flaky in production OR
2. Operator wants to use a specific model not exposed via API (e.g. Gemini 3 Pro web with sub) OR
3. Stage 3 (SaaS) approaches and end users want to bring their own subs

## Goal

Add an alternate story-step flow where the user uploads a composite grid of 6 photos to their Gemini.com / ChatGPT.com session, the model writes a story + per-pair intents, and the user pastes the structured response back into the app. App parses it and produces the same `story.json` artifact the API path produces.

## Inputs / outputs

**Inputs**
- 6 photos (already uploaded in step 1 of pipeline)
- Story-source toggle in Upload screen (scaffold from 7.4)
- Operator's web subscription session (out-of-band)

**Outputs**
- `backend/services/grid_compose.py` — builds a 2×3 composite PNG with corner labels "1, 2, 3, 4, 5, 6"
- New API endpoint `GET /projects/{id}/composite-grid` returns the PNG
- Story Review screen alternate state: "Paste your story here" textarea + parser
- A **fixed prompt** template the user copies + uses with their web sub
- Parser that extracts `arc_paragraph` + `pair_intents` from the pasted text

## Step list

### 1. `services/grid_compose.py`
- Uses Pillow (already in deps)
- Inputs: 6 image paths
- Output: 2×3 composite, ~1024×768, with corner labels rendered cleanly
- Each cell preserves aspect ratio (letterbox to 512×384 cell)
- Tests: 1 unit test confirming PNG produced + labels rendered

### 2. API endpoint
- `GET /projects/{id}/composite-grid` → PNG bytes
- Cached on disk; rebuilt only if photos change
- Operator clicks "Download composite" button

### 3. Fixed prompt template
- Stored in `data/web_sub_story_prompt.md`
- Template includes:
  - Instructions to the chat model ("look at the 6-image grid; treat them as frames 1-6 in chronological order")
  - The full set of arc-template content for the user's chosen arc
  - Required output format (markdown with specific sections so the parser works)
- Operator copies this into their Gemini/ChatGPT session

### 4. Parser
- `services/web_sub_parser.py`
- Takes pasted text, extracts:
  - `arc_paragraph`
  - `pair_intents` list (5 pairs, each with `from`, `to`, `device`, `intent`)
- Robust to minor formatting variations
- Validates against catalog (`device` must exist)
- On parse failure, returns clear error to UI (e.g. "Could not find pair 3→4 — please check format")

### 5. UI: alternate Story Review state
- When `story_source == "web-paste"`:
  - Show: "Step 1: Download composite grid + prompt template" + 2 buttons
  - Show: "Step 2: Paste output below" + textarea
  - On submit, parser runs → if valid, normalised story.json is saved → screen transitions to standard Story Review
  - If parse fails, show error inline with retry

### 6. Tests
- `services/grid_compose.py` — PNG output dimensions, label positions
- Parser — 5 cases (clean, slightly off-format, missing pair, unknown device, totally wrong)
- Frontend — Story Source = paste flow renders correctly
- Playwright — manual for this one (real subscription needed; flag as `manual` test)

### 7. Documentation
- Add `docs/operator_web_sub_flow.md` — step-by-step screenshots of how operator uses the flow
- Add to README under "operator workflow"

## Validation gates

1. **Logical:** PNG generation + parser tests green
2. **General design:** advisor pass on the fallback flow
3. **Working:** operator manually tests flow end-to-end with their real Gemini sub; produces a movie indistinguishable in eval scores from the API path
4. **No eval delta required** — this is a UX/cost path, not a quality lever

## Open questions

| Q | Default proposal | Decide when |
|---|---|---|
| Should we attempt browser automation instead of paste? | No — too brittle per `reference_gemini_web_automation.md` | Locked |
| What if user pastes text that mentions devices not in catalog? | Parser flags + asks user to correct | Step 4 |
| Composite grid resolution | 1024×768 (manageable upload size) | Step 1 |
| Where to put corner labels (top-left, top-right, etc.) | Top-left of each cell | Step 1 |

## Rollback / failure mode

If parser is consistently failing on pasted output:
1. Tighten the prompt template (more explicit format instructions)
2. Add a "manual entry" mode where operator fills in the structured fields directly via form
3. Worst case: cut this sub-plan; document that web-sub path requires API path's structured output (operator can manually copy fields)

## Memory pointers

- `reference_gemini_web_automation.md` — why we're NOT doing browser automation here
- `project_business_model.md` — service stage = this sub-plan is lower priority
- `phase_7_flow.md` — story.json contract (this sub-plan must produce same shape)
