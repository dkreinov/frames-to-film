"""Wraps `gemini-watermark.exe` into a single helper callable from every
Gemini image save point in this repo.

Contract:

    clean_if_enabled(path: Path | str) -> Path

- Overwrites the image at `path` in place when the watermark cleaner
  succeeds; returns `path` unchanged otherwise.
- Opt-out via `WATERMARK_CLEAN=off` in the environment.
- Fail-soft with one automatic retry (so at most 2 subprocess calls
  total); warnings go to stderr with the `[watermark_clean]` prefix.

See `docs/roadmap/phase_1_plan.md` for the full rationale.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

__all__ = ["clean_if_enabled"]

DEFAULT_CLI = r"D:\Programming\claude\watermark-env\Scripts\gemini-watermark.exe"
_LOG_PREFIX = "[watermark_clean]"
_RETRY_BACKOFF_S = 0.5
_MAX_CALLS = 2  # 1 initial attempt + 1 retry


def _log(msg: str) -> None:
    print(f"{_LOG_PREFIX} {msg}", file=sys.stderr)


def _resolve_cli() -> str | None:
    explicit = os.environ.get("GEMINI_WATERMARK_CLI", "").strip()
    if explicit:
        return explicit if shutil.which(explicit) else None
    return shutil.which(DEFAULT_CLI)


def clean_if_enabled(path: Path | str) -> Path:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    mode = os.environ.get("WATERMARK_CLEAN", "auto").strip().lower()
    if mode == "off":
        return p

    cli = _resolve_cli()
    if not cli:
        _log(
            f"binary not found (set GEMINI_WATERMARK_CLI or install at {DEFAULT_CLI}); "
            f"leaving {p.name} unchanged"
        )
        return p

    last_err: str | None = None
    for attempt in range(1, _MAX_CALLS + 1):
        result = subprocess.run(
            [cli, "-i", str(p), "-o", str(p)],
            capture_output=True,
        )
        if result.returncode == 0:
            return p
        last_err = (
            (getattr(result, "stderr", b"") or b"").decode(errors="replace").strip()
            or f"exit={result.returncode}"
        )
        if attempt < _MAX_CALLS:
            time.sleep(_RETRY_BACKOFF_S)

    _log(
        f"cleaner failed after {_MAX_CALLS} attempts on {p.name}: {last_err}; "
        f"leaving file unchanged"
    )
    return p
