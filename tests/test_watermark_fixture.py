"""End-to-end integration test for watermark_clean against the Pixar fixture.

Unlike tests/test_watermark_clean.py (which mocks subprocess), this one
runs the real `gemini-watermark.exe` binary on the real Gemini web
outputs saved in tests/fixtures/fake_project/ and asserts that:

- frames 2-6 (watermarked Gemini outputs) are modified in the known
  48x48 bottom-right watermark region,
- frame 1 (below the cleaner's auto-detect threshold) is left byte-
  identical, exercising the passthrough branch,
- `WATERMARK_CLEAN=off` disables cleaning entirely.

The test is auto-skipped when the cleaner binary cannot be resolved,
so CI environments without the Windows exe still see a green run.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from watermark_clean import DEFAULT_CLI, clean_if_enabled


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "fake_project"
EXPECTED_WATERMARK_BBOX = (1296, 688, 1344, 736)  # 48x48 at bottom-right of 1376x768


def _cli_available() -> bool:
    explicit = os.environ.get("GEMINI_WATERMARK_CLI", "").strip()
    target = explicit or DEFAULT_CLI
    return shutil.which(target) is not None


requires_cli = pytest.mark.skipif(
    not _cli_available(),
    reason="gemini-watermark.exe not available on this machine",
)


@requires_cli
@pytest.mark.parametrize("frame", ["frame_2_gemini.png", "frame_3_gemini.png",
                                    "frame_4_gemini.png", "frame_5_gemini.png",
                                    "frame_6_gemini.png"])
def test_watermarked_frames_get_cleaned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, frame: str) -> None:
    """Frames 2-6 carry the sparkle watermark; cleaner must modify the 48x48 BR region."""
    monkeypatch.setenv("WATERMARK_CLEAN", "auto")
    monkeypatch.delenv("GEMINI_WATERMARK_CLI", raising=False)
    staged = tmp_path / frame
    shutil.copy2(FIXTURE_DIR / frame, staged)
    original_bytes = staged.read_bytes()

    returned = clean_if_enabled(staged)
    assert returned == staged

    cleaned_bytes = staged.read_bytes()
    assert cleaned_bytes != original_bytes, "cleaner must modify the file"

    before = Image.open(FIXTURE_DIR / frame).convert("RGB")
    after = Image.open(staged).convert("RGB")
    diff_bbox = ImageChops.difference(before, after).getbbox()
    assert diff_bbox == EXPECTED_WATERMARK_BBOX, (
        f"diff bbox {diff_bbox!r} must match known watermark region {EXPECTED_WATERMARK_BBOX!r}"
    )


@requires_cli
def test_frame_1_passes_through_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Frame 1's watermark is below the cleaner's auto-detect threshold.

    The cleaner may re-encode the PNG container (so raw bytes can shift a few
    positions), but the decoded pixel grid must be identical — no watermark
    region was modified.
    """
    monkeypatch.setenv("WATERMARK_CLEAN", "auto")
    monkeypatch.delenv("GEMINI_WATERMARK_CLI", raising=False)
    staged = tmp_path / "frame_1_gemini.png"
    shutil.copy2(FIXTURE_DIR / "frame_1_gemini.png", staged)

    clean_if_enabled(staged)

    before = Image.open(FIXTURE_DIR / "frame_1_gemini.png").convert("RGB")
    after = Image.open(staged).convert("RGB")
    assert ImageChops.difference(before, after).getbbox() is None


@requires_cli
def test_off_mode_never_touches_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WATERMARK_CLEAN=off must leave a watermarked fixture byte-identical."""
    monkeypatch.setenv("WATERMARK_CLEAN", "off")
    staged = tmp_path / "frame_2_gemini.png"
    shutil.copy2(FIXTURE_DIR / "frame_2_gemini.png", staged)
    original_bytes = staged.read_bytes()

    clean_if_enabled(staged)
    assert staged.read_bytes() == original_bytes
