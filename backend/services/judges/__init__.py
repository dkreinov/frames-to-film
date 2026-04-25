"""Three-tier judge stack — Phase 7.1.

Quality-layer services that score pipeline outputs against rubrics:

- `prompt_judge`: pre-render gate — scores prompt-image alignment 1-5.
  Lets the pipeline reject bad prompts before spending $0.084 on Kling.
- `clip_judge`: post-render — samples 3 frames from a 5s clip and scores
  visual quality + anatomy + prompt-fidelity. Drives the optional re-roll.
- `movie_judge`: post-stitch — text-only reasoning over per-clip judge
  results + story arc + brief. Identifies the weakest seam.

All three return a `JudgeScore` envelope (see `base.py`). Eval harness
(7.2) reads that shape; calibration (7.3) refines the rubric prompts.
"""
from backend.services.judges.base import JudgeScore
from backend.services.judges.clip_judge import score_clip
from backend.services.judges.movie_judge import score_movie
from backend.services.judges.prompt_judge import score_prompt

__all__ = ["JudgeScore", "score_prompt", "score_clip", "score_movie"]
