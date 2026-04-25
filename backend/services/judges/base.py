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
# Verified against actual Google Cloud Console billing 2026-04-25
# (My Billing Account_Reports, 2026-04-18 — 2026-04-25.csv). Earlier
# estimates were 10-12x low because:
#   1. Gemini 2.5/3 emit "thinking" tokens NOT exposed in the SDK's
#      candidates_token_count. Real billable output ≈ visible × 5-10.
#   2. gemini-3-flash-preview is BILLED at $0.50/$3 per M (was labeled
#      "free during preview" — wrong).
# Going forward: trust billing dashboard, not SDK self-report.

_PRICE_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    # in_per_M, out_per_M  --  effective rates (incl. thinking tokens
    # where applicable, derived from actual ₪/token billing)
    "gemini-2.5-flash-lite": (0.10, 0.40),         # confirmed via bill
    "gemini-2.5-flash": (0.30, 2.50),              # +thinking surcharge
    "gemini-3-flash-preview": (0.50, 3.00),        # NOT free; was wrong
    "gemini-3-flash": (0.50, 3.00),
    "gemini-2.5-pro": (1.25, 10.00),               # confirmed via bill
    "gemini-3-pro-preview": (2.00, 12.00),         # treat as priced; verify
    "gemini-3-pro": (2.00, 12.00),
    "gemini-2.5-flash-image": (0.30, 30.00),       # image OUTPUT is the killer; ~$0.30 per generated image
    "deepseek-chat": (0.14, 0.28),                 # V4 Flash
    "deepseek-v4-flash": (0.14, 0.28),
    "deepseek-v4-pro": (1.74, 3.48),
    "deepseek-reasoner": (0.55, 2.19),             # legacy R1; retires 2026-07
    # Qwen via DashScope international (qwen.ai/apiplatform)
    "qwen-vl-plus": (0.21, 0.63),
    "qwen-vl-max": (0.52, 2.08),
    "qwen3-vl-plus": (0.50, 1.50),
    "qwen3-vl-235b-a22b-thinking": (0.26, 0.90),
    # Kimi via Moonshot (api.moonshot.ai)
    "moonshot-v1-8k-vision-preview": (0.30, 0.90),
    "moonshot-v1-128k-vision-preview": (0.60, 1.80),
    "kimi-k2.5": (0.60, 2.50),
    "kimi-k2.6": (0.74, 4.66),
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
