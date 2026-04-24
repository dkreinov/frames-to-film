# frames-to-film

Internal operator tool for producing short photo-montage movies.
You drop 3–10 customer photos, arrange their order, and the AI
pipeline auto-writes prompts, renders each transition via Kling O3
(fal.ai), and stitches the result. Mock mode is free for testing
the flow; api mode is paid and produces real clips.

The service you sell to customers is your concern. This repo is
the factory floor.

![wizard tour](docs/design/golden/phase_6_journey.gif)

## Use modes

| Mode | Cost | Shape |
|---|---|---|
| **mock** | free (ffmpeg black-frame stubs) | Testing flow, UI changes, regression |
| **api** | ~$0.42 per 5s clip via fal.ai Kling O3 | Real customer deliverables |

Typical 6-photo project = 5 transitions × 5s = **~$2.10 per movie** in api mode.

## What stays manual, what's automated

Manual (human judgment):
- **Photo order** — narrative choice; drag-drop on the Storyboard screen
- **Final accept/redo per clip** — the Review screen (quality gate before stitch)

Automated (AI, operator shouldn't touch):
- **Prompt writing** — Gemini writes one per consecutive pair
- **Video generation** — Kling O3 first-frame → last-frame interpolation
- **4:3 → 16:9 normalize** — per-stage, mock-mode today (productized api mode = Phase 7)
- **Stitch** — ffmpeg stream-copy concat of approved clips

If any AI step misbehaves, the UI should give you a per-pair lever
(regenerate this prompt, retry this clip) rather than force a full
restart. Several of those levers don't exist yet — see "Automation
gaps" below.

## Running it locally

Prereqs: Python 3.12, Node 20, `ffmpeg` on PATH.

```bash
# Backend (terminal 1)
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Frontend (terminal 2)
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. Walk the wizard: Upload → Prepare →
Storyboard (order photos) → Generate → Review (verdicts) → Export.

## Keys — paste once in Settings, they live in browser localStorage

- **fal.ai** — https://fal.ai/dashboard/keys (pay-as-you-go, no
  minimum). Paste into `/settings` → "fal.ai API key" → Save. Then
  flip "Generate videos" to api.
- **Gemini** — https://aistudio.google.com/apikey (free tier for
  prompts generation is fine). Paste into `/settings` → "Gemini API
  key" → Save. Then flip "Generate prompts" to api.

Keys travel as `X-Fal-Key` / `X-Gemini-Key` request headers from
the browser to the backend. Never stored server-side.

## Automation gaps (Phase 7+ roadmap)

These are the hand-cranks that make the current wizard annoying at
scale. Planned as individual sub-plans:

- **Auto-advance between AI stages**. Today the operator clicks
  "Generate videos" after prompts load, then "Stitch & Export"
  after verdicts. Should be: hit one button after ordering, walk
  away, come back to a download link (unless a clip genuinely
  needs human review).
- **Per-pair progress in Generate**. Today: single spinner until
  all clips done. Should be: "Pair 1/5 ✓ | Pair 2/5 rendering
  (~45s) | Pair 3/5 queued | …".
- **Per-pair retry + per-prompt regen**. If pair 3 fails or its
  prompt reads wrong, fix just that pair, not the whole batch.
- **Batch dashboard** (multi-customer): row-per-project list with
  status + download column. Queue multiple customers, come back
  when all done.
- **Idempotent state machine**. Today re-clicking Generate can
  re-fire the whole batch. Should detect "this pair already
  rendered successfully — skip it".

Ordering + final verdict stay manual.

## Architecture

FastAPI backend + React/Vite frontend. Jobs run as background tasks
against a sqlite ledger (`backend/db.py`). Per-stage services in
`backend/services/` (prepare, extend, prompts, generate, stitch,
kling_fal). The frontend wizard is a 5-route React Router app under
`frontend/src/routes/`.

Full details: [`docs/architecture.md`](docs/architecture.md).
Frozen component contracts: [`docs/design.md`](docs/design.md).

## CI

Three GitHub Actions jobs on every push, all mock mode (no API keys
needed): backend pytest, frontend vitest + tsc, Playwright E2E.

Config: `.github/workflows/test.yml`. Status:
![ci](https://github.com/dkreinov/frames-to-film/actions/workflows/test.yml/badge.svg)

## Phase status

Shipped: Phase 1 (watermark cleaner, now legacy) → Phase 2 (FastAPI
engine + mock mode) → Phase 3 (prompt library) → Phase 4 (React
wizard, 6 sub-plans) → Phase 5 (fal.ai Kling O3) → Phase 6 Sub-Plans
1+2 (E2E + CI green, legacy move).

Next for Phase 6: `/app-design` + `/frontend-design` polish,
Vercel deploy.

Then **Phase 7** is the automation-gaps list above.

See [`docs/roadmap/phases.md`](docs/roadmap/phases.md) for the full
phase plan.

## Legacy

`legacy/` archives pre-FastAPI work (Streamlit review UI, Kling JWT
direct client, Phase-1 watermark scripts). Not imported by the
active backend; not covered by CI. Kept for reference + personal-use
CLI scripts.
