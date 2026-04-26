# Project skeleton

Copy this folder to start a new movie project. See `docs/PROJECT_SCHEMA.md` for the full spec.

## Quick start

1. **Copy the template** (pick a URL-safe lowercase slug):
   ```bash
   cp -r projects/_template projects/<slug>
   ```

2. **Fill `metadata/project.json`** — replace `__SLUG__`, `__NAME__`, `__CREATED_AT__` (ISO date `YYYY-MM-DD`), and any tags.

3. **Drop original photos** into `inputs/` in the order you want them displayed (filename order is the display order).

4. **Drop a soundtrack candidate** into `audio/`, then set `audio_track` in `project.json` to its filename when chosen.

5. **Run the pipeline** — the backend will populate `prompts/`, `extended/`, `clips/raw/` automatically.

6. **Operator review** — pick the best take per pair into `clips/selected/`, then stitch to `final/<slug>-v1.mp4`.

7. **Deliver** — zip the final cut into `exports/<slug>-v1.zip`.

## Subfolder cheat sheet

| Folder | Purpose |
|---|---|
| `inputs/` | Original photos (operator-uploaded, never overwritten) |
| `extended/` | In-between / outpainted frames generated to bridge consecutive inputs |
| `prompts/` | Per-pair prompts JSON + preview stills |
| `clips/raw/` | All generator outputs (failed and successful takes) |
| `clips/selected/` | Operator/judge-picked single take per pair (input to stitcher) |
| `audio/` | Soundtrack candidates and chosen track |
| `final/` | Stitched movies, versioned (`<slug>-v1.mp4`, `<slug>-v2.mp4`, ...) |
| `exports/` | Zip bundles for client delivery |
| `metadata/` | All persistent JSON state + per-stage logs |
