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

- The app does not submit new Kling jobs yet.
- The redo queue is a handoff for the next regeneration pass.
- The tool is local-first and stores data in JSON, not a database.
