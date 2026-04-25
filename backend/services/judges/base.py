"""Shared types + helpers for the judge stack.

`JudgeScore` is the envelope every judge returns. The eval harness (7.2)
reads this shape; never break it without a `version` bump + migration.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

JudgeName = Literal["prompt_judge", "clip_judge", "movie_judge"]


class JudgeScore(BaseModel):
    """Common envelope for all three judges.

    `scores` is a flexible dict because each judge populates a different
    subset of dimensions:
        prompt_judge → {"prompt_image_alignment": float}
        clip_judge   → {"visual_quality": float, "anatomy_ok": bool,
                        "style_consistency": float}
        movie_judge  → {"story_coherence": float,
                        "character_continuity": float,
                        "visual_quality": float, "emotional_arc": float}

    All numeric scores are 1.0-5.0 floats. `anatomy_ok` is a bool.
    `weakest_seam` is movie_judge only — the 1-indexed pair number with
    the worst transition.
    """

    judge: JudgeName
    version: str = "v1"
    scores: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""
    weakest_seam: int | None = None
    model_used: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def is_failing(self, threshold: float = 2.0) -> bool:
        """True if any numeric score is below `threshold`. Used by the
        re-roll decision in clip_judge wiring (7.5).

        Excludes bool (which subclasses int in Python) so that
        ``anatomy_ok: True`` doesn't get counted as ``1 < threshold``.
        """
        for v in self.scores.values():
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)) and v < threshold:
                return True
        return False


# --- Token-cost tables (per 1M tokens; refresh when prices move) -----
#
# Source: docs/roadmap/reference_model_prices_2026_04 (memory) snapshot
# 2026-04-25. Update here when memory updates.

_PRICE_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    # in_per_M, out_per_M
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-3-flash-preview": (0.0, 0.0),   # free during preview; pricing TBA
    "gemini-3-flash": (0.50, 3.00),         # post-GA placeholder
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-3-pro-preview": (0.0, 0.0),     # free during preview
    "gemini-3-pro": (2.00, 12.00),
    "deepseek-chat": (0.14, 0.28),          # V4 Flash via deepseek-chat alias
    "deepseek-v4-flash": (0.14, 0.28),
    "deepseek-v4-pro": (1.74, 3.48),
    "deepseek-reasoner": (0.55, 2.19),      # legacy R1; retires 2026-07
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return USD cost for a call given the token counts.

    Returns 0.0 if the model is unknown — callers can still log the call
    even if pricing isn't tabulated yet.
    """
    rates = _PRICE_PER_M_TOKENS.get(model)
    if not rates:
        return 0.0
    in_per_m, out_per_m = rates
    return (input_tokens / 1_000_000) * in_per_m + (output_tokens / 1_000_000) * out_per_m
