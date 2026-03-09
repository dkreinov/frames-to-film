# Olga Movie

This repo has two clear areas now:

- Active product workflow at the repo root:
  - `outpaint_images.py`
  - `outpaint_16_9.py`
  - `generate_all_videos.py`
  - `review_app.py`
  - `redo_runner.py`
  - `concat_videos.py`
- Archived experiments and older one-off utilities under `legacy/`

## Active Flow

1. Normalize source photos into `outpainted/` with `outpaint_images.py`
2. Expand numbered story frames into `kling_test/` with `outpaint_16_9.py`
3. Generate resumable clip batches with `generate_all_videos.py`
4. Review clips and queue retries with `review_app.py`
5. Run retries with `redo_runner.py`
6. Stitch approved winners with `concat_videos.py`

## Project Layout

- `docs/architecture.md`: full pipeline architecture and historical notes
- `docs/review-app.md`: Streamlit review app usage
- `image_pair_prompts.py`: pair-specific prompt map used by generation and redo
- `legacy/image_prep/`: older image-prep utilities kept for reference
- `legacy/video_generation/`: older manual and variant Kling generators

## Review App

Install the local review dependencies:

```powershell
python -m pip install -r requirements-review.txt
```

Run the app:

```powershell
python -m streamlit run review_app.py
```

The review UI now includes rebuilt-version compare mode with up to 4 videos, a larger focused compare view, and shared compare playback controls where the browser allows them. See `docs/review-app.md` for the full workflow.
## Gemini Pro Batch Extension

To extend a whole folder through Gemini Web and always finish with `Redo with Pro`, use:

```powershell
C:\Users\nishtiak\AppData\Local\Programs\Python\Python312\python.exe -m pip install playwright
C:\Users\nishtiak\AppData\Local\Programs\Python\Python312\python.exe D:\Programming\olga_movie\gemini_pro_extend.py --source-dir D:\Programming\olga_movie\Olia_continue --output-dir D:\Programming\olga_movie\Olia_continue\extend
```

Notes:

- The script opens a dedicated Chrome profile under [D:\Programming\olga_movie\.gemini_chrome_profile](D:\Programming\olga_movie\.gemini_chrome_profile).
- On the first run, log into Gemini in that browser window, then press Enter in the terminal.
- Existing files in the output folder are skipped unless you pass `--force`.
