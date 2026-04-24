"""Veo (Gemini Pro web) Playwright adapter — Phase 5 Sub-Plan 1 stub.

This module declares the interface Phase 5 Sub-Plan 2 will implement.
Every real-browser method raises `WebModeNotImplemented` so that the
generate-videos runner can catch it and convert "not yet wired" into a
user-visible job error, instead of a 500 crash or a bare ValueError.

Sub-Plan 2 will replace each `raise WebModeNotImplemented(...)` with a
real Playwright step against an authenticated Chrome profile — the
profile pattern from `.gemini_chrome_profile/` (see
`docs/design/manual/...` memory note). The method names and signatures
on this class are a frozen contract: Sub-Plan 2 MUST NOT rename them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class WebModeNotImplemented(NotImplementedError):
    """Raised by adapter methods until Phase 5 Sub-Plan 2 wires them up.

    The runner catches this specific subclass and writes a clean job
    error. Real bugs (ValueError, RuntimeError, Playwright timeouts)
    are intentionally NOT caught — they surface as 500s so they get
    noticed and fixed.
    """


_NOT_IMPL_MSG = (
    "Phase 5 Sub-Plan 2 — authenticated browser profile required. "
    "Flip 'Generate videos' to api or mock mode in Settings."
)


class VeoWebAdapter:
    """Interface stub. Sub-Plan 2 fills in each method with Playwright."""

    def authenticate(self) -> None:
        """Attach to an existing `.gemini_chrome_profile/` or sign in."""
        raise WebModeNotImplemented(_NOT_IMPL_MSG)

    def upload_frame(self, path: Path) -> str:
        """Upload a single frame and return the Gemini-side reference URL."""
        raise WebModeNotImplemented(_NOT_IMPL_MSG)

    def request_generation(
        self,
        frame_a_url: str,
        frame_b_url: str,
        prompt: str,
    ) -> str:
        """Kick off one Veo generation; return the job reference."""
        raise WebModeNotImplemented(_NOT_IMPL_MSG)

    def download_clip(self, job_ref: str) -> bytes:
        """Poll for completion and return the raw mp4 bytes."""
        raise WebModeNotImplemented(_NOT_IMPL_MSG)

    def cleanup(self) -> None:
        """Tear down the browser context. Safe to call on failure paths."""
        raise WebModeNotImplemented(_NOT_IMPL_MSG)

    # Convenience hook so callers can use `with VeoWebAdapter(): ...`
    def __enter__(self) -> "VeoWebAdapter":
        return self

    def __exit__(self, *exc_info: Any) -> None:  # noqa: ANN401
        try:
            self.cleanup()
        except WebModeNotImplemented:
            # On the stub, cleanup is a no-op; don't mask the real error.
            pass
