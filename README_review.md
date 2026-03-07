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
3. If the clip is usable, choose `Approve`.
4. If the clip should be regenerated, choose `Redo`, select issue tags, and add a note if needed.
5. If you are unsure, choose `Needs discussion`.
6. If multiple versions exist, use `Compare versions` and mark the winning version.
7. Open the `Redo queue` tab to see the clips that should be regenerated next.

If a retried version is still listed under `Waiting for review`, open that pair, select the retried version, and use `Accept selected version and clear waiting review`. That saves an `Approve` review for the retry and removes the stale waiting entry.

## Run Queued Retries From The App

The `Redo queue` tab now has two controls:

- `Preview queued retries`: shows the next version number, output filename, and retry prompt before anything is submitted
- `Run queued retries`: sends only `queued` items to Kling
- `Queued items to run`: lets you choose which queued retries to preview or run, so you do not have to spend credits on the whole queue at once

To actually run queued retries, your `.env` must contain valid Kling credentials.
If your `.env` also contains a `gemini` or `GEMINI_API_KEY` value, the retry prompt is first rewritten by Gemini from the base pair prompt plus the review feedback. If no Gemini key is available, the app falls back to the rule-based retry prompt builder.

Important behavior:

- after a retry succeeds, that queue item changes from `queued` to `waiting_review`
- `waiting_review` items stay visible in the app, but they are not sent to Kling again
- once the new version is reviewed in the app, the old `waiting_review` entry is removed automatically

This prevents the queue from looping on already-generated retries.

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
