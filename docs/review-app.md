# Review Tool

This is a small local Streamlit app for reviewing generated movie clips, marking good ones as approved, and collecting bad ones into a redo queue.

## What It Does

- Loads segment videos from `kling_test/videos/`
- Treats the current `seg_<pair>.mp4` files as version `v1`
- Supports future retry files such as `seg_<pair>_v2.mp4`
- Lets a reviewer:
  - approve a clip
  - request a redo
  - mark a clip as needing discussion
  - choose issue tags
  - write an optional note
  - pick the winning version for a pair
- Saves review state under `pipeline_runs/local-review-run/`

## Files Written By The App

- `pipeline_runs/local-review-run/reviews.json`
- `pipeline_runs/local-review-run/redo_queue.json`
- `pipeline_runs/local-review-run/winners.json`

## Install

If `python` works in your shell:

```powershell
python -m pip install -r requirements-review.txt
```

If this machine does not expose `python` directly, use the full interpreter path:

```powershell
C:\Users\nishtiak\AppData\Local\Programs\Python\Python312\python.exe -m pip install -r requirements-review.txt
```

The review app now also includes the in-app Kling retry runner, so the review environment installs:

- `streamlit`
- `requests`
- `python-dotenv`
- `google-genai`

## Run

If `python` works in your shell:

```powershell
python -m streamlit run review_app.py
```

If you need the explicit interpreter:

```powershell
C:\Users\nishtiak\AppData\Local\Programs\Python\Python312\python.exe -m streamlit run D:\Programming\olga_movie\review_app.py
```

## Review Flow

1. Open the app and pick a clip from the sidebar.
2. Watch the clip and compare it with the start and end frames.
3. If the clip is usable, choose `Approve`. The primary button becomes `Approve and next`.
4. If the clip should be regenerated, choose `Redo`, select issue tags, and add a note if needed.
5. If you are unsure, choose `Needs discussion`.
6. If multiple versions exist, open `Compare versions side by side` to compare them before picking a winner.
7. The compare picker supports up to 4 versions:
   - 1 version: large single preview
   - 2 versions: side by side
   - 3 or 4 versions: a 2x2 compare grid
8. Use `Open large compare view` when you want the compare videos to take over most of the review tab. Use `Back to review details` to return.
9. The compare toolbar also attempts shared `Play all`, `Pause all`, `Restart all`, and `Fullscreen compare` controls for the visible compare videos.
10. If your browser blocks shared media controls, use each player's native controls and fullscreen button instead.
11. Open the `Redo queue` tab to see the clips that should be regenerated next.
12. Open the `Extend images` tab when you want to widen still images for the pipeline without using the Gemini image API directly.

Tip:
- The sidebar labels are reviewer-focused:
  - `Unreviewed` means the clip still needs a first pass
  - `Needs redo` means the latest version has already been marked for another generation pass
  - `New version ready` in the redo queue means a retried clip came back and is ready to judge
- The main review panel now hides technical details under `Advanced review options` so the decision controls stay visible.
- The review panel shows progress counters and save messages such as how many clips are still unreviewed and which clip you moved to next.
- Use the sidebar filter `Rebuilt clips` to show only pairs that already have a retried version like `v2` or `v3`.
- The compare controls are local to the compare area. If the shared playback buttons do not work in your browser, the fallback is still safe: focused compare mode plus each video's built-in playback and fullscreen controls.

If a retried version is still listed under `New version ready`, open that pair, select the retried version, and use the accept button for that version. That saves an `Approve` review for the retry and removes the stale waiting entry.

## Run Queued Retries From The App

The `Redo queue` tab now has two controls:

- `Preview queued retries`: shows the next version number, output filename, and retry prompt before anything is submitted
- `Run queued retries`: sends only `queued` items to Kling
- `Queued items to run`: lets you choose which queued retries to preview or run, so you do not have to spend credits on the whole queue at once
- `Generate new prompt`: asks the automatic prompt builder to create a fresh retry prompt
- `Use edited prompt for retry`: turns the currently edited prompt into the manual override for that retry
- `Return to automatic prompt`: removes the saved manual override and restores the automatic rewrite

To actually run queued retries, your `.env` must contain valid Kling credentials.
If your `.env` also contains a `gemini` or `GEMINI_API_KEY` value, the retry prompt is first rewritten by Gemini from the base pair prompt plus the review feedback. If no Gemini key is available, the app falls back to the rule-based retry prompt builder.

Important behavior:

- after a retry succeeds, that queue item changes from `queued` to `waiting_review`
- `waiting_review` items stay visible in the app, but they are not sent to Kling again
- once the new version is reviewed in the app, the old `waiting_review` entry is removed automatically
- when a queued retry has a saved prompt override, preview and run use that manual prompt instead of the Gemini or rule-based rewrite
- the prompt remains automatic until the user presses `Use edited prompt for retry`
- `Generate new prompt` creates a fresh automatic prompt first, so the user can review or edit it before deciding to override

This prevents the queue from looping on already-generated retries.

## Extend Images With Gemini Web

The `Extend images` tab is for the manual Gemini Web workflow:

- choose `4:3 from raw images` to prepare files for `outpainted/`
- choose `16:9 from 4:3 images` to prepare files for `kling_test/`
- choose a source folder and pick one or more images from the preview gallery
- open Gemini Web from the app
- use the prefilled prompt shown for the active image
- download the finished image from Gemini
- upload that finished image back into the app

The app saves the uploaded result into the correct pipeline folder with the expected filename, so the rest of the pipeline can pick it up.

## Review Decisions

- `Approve`: the clip is good enough for the final movie.
- `Redo`: the clip should be regenerated.
- `Needs discussion`: the clip has problems or ambiguity that should be reviewed by a human before deciding.

## Common Issue Tags

- `Face looks bad`
- `Identity drift`
- `Hands or body look wrong`
- `Transition is bad`
- `Scenario is wrong`
- `Background is wrong`
- `Style mismatch`
- `Too fast`
- `Too slow`
- `Artifacts`
- `Emotion is wrong`
- `Prompt ignored`

## Notes

- The app can preview and submit queued retries to Kling.
- The retry prompt uses Gemini rewrite first when available, then falls back to the local rule-based prompt builder.
- The tool is local-first and stores data in JSON, not a database.
