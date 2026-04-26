# Project Schema — `projects/{slug}/` canonical layout

**Status:** authoritative as of 2026-04-26 (Sub-plan A).
**Code consumers:** `backend/services/project_schema.py` (created in Sub-plan B) is the runtime source of truth — keep this doc and that module in lockstep.

This document defines how a single movie project's files are organized on disk. It exists so operators, future agents, and downstream code do not have to reverse-engineer a folder layout from scattered code paths. **Every new project MUST start by copying `projects/_template/`.**

---

## Folder layout

```
projects/
├── _template/                         # operator-copyable skeleton; do not edit per-project
│   ├── inputs/                        # original photos uploaded by operator
│   ├── extended/                      # in-between / outpainted frames (intermediate)
│   ├── prompts/                       # per-pair prompts JSON + generated stills
│   ├── clips/
│   │   ├── raw/                       # all generator outputs (kling, wan, etc.)
│   │   └── selected/                  # operator/judge-picked best take per pair
│   ├── audio/                         # soundtrack files for this project
│   ├── final/                         # stitched mp4s (versioned: <slug>-v1.mp4, -v2.mp4, ...)
│   ├── exports/                       # zip bundles for client delivery
│   ├── metadata/
│   │   ├── project.json               # ProjectMeta (slug, name, status, ...)
│   │   ├── story.json                 # arc + pair_intents (Phase 7.4 output)
│   │   ├── judges.json                # clip + movie judge scores
│   │   ├── costs.json                 # per-stage USD spend
│   │   └── logs/                      # per-run logs (kling_2026-04-26.log, ...)
│   └── README.md                      # operator instructions for this skeleton
│
├── _archive/                          # historical pipeline_runs UUIDs; gitignored contents
│   └── {uuid}/                        # frozen experiment snapshots (read-only reference)
│
└── {slug}/                            # one folder per real project (e.g. olga, anna_50, ...)
    └── (same subfolders as _template/, populated as the pipeline runs)
```

**Canonical project root path:**
- Operator-driven phase (current): `projects/{slug}/`
- Multi-user phase (later): `projects/{user_id}/{slug}/` — drilled in by `backend/services/project_schema.project_root()`.

---

## Subfolder purpose

| Subfolder | What lives there | Naming convention |
|---|---|---|
| `inputs/` | Original photos uploaded by the operator. The pipeline never overwrites these. | Keep original filenames OR renumbered `01.jpg`, `02.jpg`, ... if operator chooses. Numbering = display order. |
| `extended/` | In-between / outpainted frames generated to bridge two consecutive inputs (Phase 5+ outpainting, Olia "extend" frames). Subfolders allowed for multiple sources (e.g. `extended/from_olia_extend/`). | `{from_idx}_to_{to_idx}.jpg` or original generator name. |
| `prompts/` | Per-pair prompts JSON (`pair_{i}_to_{j}.json`) + any preview stills the prompt-writer rendered (`pair_{i}_to_{j}_preview.png`). | `pair_<from>_to_<to>.{json,png}` |
| `clips/raw/` | Every generated clip the pipeline produced, including failed/judged-low takes. Generator-tagged. | `pair_<from>_to_<to>__<generator>__<ts>.mp4` (e.g. `pair_3_to_4__kling__1746543210.mp4`) |
| `clips/selected/` | Operator/judge-approved single take per pair; this is what the stitcher reads. | `pair_<from>_to_<to>.mp4` (no generator suffix; symlink or copy from raw) |
| `audio/` | Soundtrack candidates / picks for this project. | Original filename; the chosen track is referenced from `metadata/project.json:audio_track`. |
| `final/` | Stitched movies. Versioned. | `{slug}-v{n}.mp4` (e.g. `olga-v1.mp4`, `olga-v2.mp4`) |
| `exports/` | Zip bundles for client delivery (final mp4 + selects + brief). | `{slug}-v{n}.zip` |
| `metadata/` | All persistent JSON state for the project. | See "project.json schema" below; other files are pipeline-defined. |
| `metadata/logs/` | Per-stage / per-run log captures. | `<stage>_<YYYY-MM-DD>.log` (e.g. `kling_2026-04-26.log`) |

---

## `project.json` schema

`projects/{slug}/metadata/project.json` — the operator-edited identity record. Format mirrors `backend.services.project_schema.ProjectMeta` (created in Sub-plan B).

```json
{
  "slug": "olga",
  "name": "Olga life montage",
  "created_at": "2026-04-26",
  "status": "in_progress",
  "tags": ["legacy", "real-asset-validation"],
  "audio_track": "Forever Young (Piano Version).mp3",
  "source": "operator_upload"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `slug` | `str` | yes | URL-safe project id; matches folder name. Pattern: `^[a-z0-9][a-z0-9_-]*$`, max 64 chars. |
| `name` | `str` | yes | Human-readable project title shown in operator UI. |
| `created_at` | ISO date (`YYYY-MM-DD`) | yes | Date the project was started. |
| `status` | enum | yes | `draft` \| `in_progress` \| `review` \| `delivered` \| `archived`. |
| `tags` | `list[str]` | no | Free-form tags (e.g. `["legacy"]`, `["client:acme"]`). Default `[]`. |
| `audio_track` | `str` or `null` | no | Filename inside `audio/`; the stitcher uses this as the soundtrack. `null` = no music yet. |
| `source` | `str` | no | Where the project originated (`operator_upload`, `legacy_migration`, `web_import`, ...). Default `operator_upload`. |

Other JSON files in `metadata/` (`story.json`, `judges.json`, `costs.json`) are pipeline-managed and not operator-editable except for review.

---

## Tracked vs gitignored

The repo's existing `.gitignore` already drops media globally (`*.jpg`, `*.jpeg`, `*.png`, `*.mp4`, `*.mp3`, `*.zip`, `*.pdf`, `*.html`, `*.jsonl`). That rule covers everything heavy inside `projects/`.

**What ends up tracked under `projects/`:**

- `projects/_template/**/.gitkeep` — empty markers preserving the skeleton structure
- `projects/_template/metadata/project.json` — placeholder JSON (with `__SLUG__` / `__NAME__` / `__CREATED_AT__`)
- `projects/_template/README.md`
- `projects/{slug}/metadata/*.json` — the operator-editable + pipeline-managed JSON state
- `projects/{slug}/metadata/logs/*.log` — text logs (small, human-readable)
- `projects/{slug}/README.md` — optional per-project notes
- `projects/{slug}/.gitkeep` markers in empty subfolders

**What is NEVER tracked:**

- All media files in `inputs/`, `extended/`, `clips/`, `audio/`, `final/`, `exports/` (auto-ignored by extension globs).
- `prompts/*.png` preview stills (`*.png` is globally ignored).
- **Everything inside `projects/_archive/{uuid}/`** — explicit `projects/_archive/**` rule (added in Sub-plan A Step 6) keeps historical experiment dumps fully out of git, even their JSON metadata. The archive root has a single `.gitkeep` so the directory itself stays present.

If a JSON or YAML inside an archived UUID needs to be preserved, copy it out to `docs/` or `projects/{slug}/metadata/` before relying on the archive.

---

## Project lifecycle

The standard happy path for a paying-client movie:

1. **Create**
   `cp -r projects/_template projects/{slug}` — operator picks a slug.
   Edit `projects/{slug}/metadata/project.json` to fill `slug`, `name`, `created_at`, optional `tags`.

2. **Upload originals**
   Drop the operator's photos into `projects/{slug}/inputs/`. Order matters — the filename order is the display order.

3. **Story + prompts** (Phase 7.4 + 7.5)
   Backend writes `projects/{slug}/metadata/story.json` and per-pair prompts under `projects/{slug}/prompts/pair_<i>_to_<j>.json`.

4. **Generate clips**
   Generator (Kling, Wan, ...) writes raw outputs to `projects/{slug}/clips/raw/pair_<i>_to_<j>__<gen>__<ts>.mp4`.

5. **Judge + select**
   Clip judge writes scores into `projects/{slug}/metadata/judges.json`.
   Operator (or auto-pick) places the chosen take per pair into `projects/{slug}/clips/selected/pair_<i>_to_<j>.mp4`.

6. **Stitch**
   Stitcher reads `clips/selected/` + the soundtrack referenced by `metadata/project.json:audio_track` from `audio/` → writes `projects/{slug}/final/{slug}-v{n}.mp4`.

7. **Export + deliver**
   Operator zips `final/{slug}-v{n}.mp4` (+ optional metadata) into `projects/{slug}/exports/{slug}-v{n}.zip` and ships to client.

8. **Archive**
   Once delivered: set `metadata/project.json:status` to `delivered` (or `archived` after a retention window). The folder stays in `projects/{slug}/`; do NOT move into `_archive/`. `_archive/` is reserved for legacy experiments, not deliveries.

---

## Migration from legacy `pipeline_runs/`

Before Sub-plan A, the repo wrote per-run state into `pipeline_runs/local/{user_id}/{uuid}/` with the following subfolders:

| Legacy path | New path | Owner |
|---|---|---|
| `pipeline_runs/local/{uuid}/sources/` | `projects/{slug}/inputs/` | Sub-plan A migrated Olga; Sub-plan B updates code |
| `pipeline_runs/local/{uuid}/outpainted/` | `projects/{slug}/extended/` | same |
| `pipeline_runs/local/{uuid}/kling_test/videos/` | `projects/{slug}/clips/raw/` | same |
| `pipeline_runs/local/{uuid}/run.json`, `prompts.json` | `projects/{slug}/metadata/*.json` (split per concern) | same |

**Historical experiments:** the 10 UUID-named folders that lived under `pipeline_runs/local/` are preserved at `projects/_archive/{uuid}/` for reference. Their contents are gitignored — the archive is for browsing on disk, not for re-running the pipeline.

**Code update timing:** during Sub-plan A, backend code still writes to `pipeline_runs/`. Sub-plan B (`plans/plan-B-20260426-1500.md`) renames the constants and updates ~60 files so the backend reads/writes the new schema. Until Sub-plan B completes, any pipeline run will recreate `pipeline_runs/local/{uuid}/` next to `projects/`. That is expected and reconciled by Sub-plan B.
