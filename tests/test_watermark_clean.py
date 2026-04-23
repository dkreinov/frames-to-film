"""Unit tests for the watermark_clean helper (Phase 1 / Step 3 — TDD Red).

These tests define the contract for `clean_if_enabled(path)` before the
implementation exists. Running pytest against this file now must FAIL
with `ModuleNotFoundError` for the missing `watermark_clean` module.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# Fixture: a tiny valid image file on disk to pass to the helper.
@pytest.fixture
def image_file(tmp_path: Path) -> Path:
    path = tmp_path / "frame.png"
    # 1-pixel PNG, enough for path existence checks.
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf"
        b"\xc0\x00\x00\x00\x03\x00\x01\x5c\xcd\xff\x69\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return path


def _mock_run_rc(rc: int) -> MagicMock:
    """Return a MagicMock subprocess.CompletedProcess with a given return code."""
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.returncode = rc
    m.stdout = b""
    m.stderr = b""
    return m


class TestCleanIfEnabled:

    def test_case_1_auto_success_calls_cli_with_in_equals_out(
        self, image_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Case 1: WATERMARK_CLEAN=auto + subprocess returns 0 → subprocess called with -i path -o path, returns path."""
        from watermark_clean import clean_if_enabled

        monkeypatch.setenv("WATERMARK_CLEAN", "auto")
        with patch("watermark_clean.shutil.which", return_value=r"C:\fake\cli.exe"):
            with patch("watermark_clean.subprocess.run", return_value=_mock_run_rc(0)) as mock_run:
                result = clean_if_enabled(image_file)

        assert result == image_file
        assert mock_run.call_count == 1
        args, _ = mock_run.call_args
        cmd = args[0]
        assert "-i" in cmd and "-o" in cmd
        i_val = cmd[cmd.index("-i") + 1]
        o_val = cmd[cmd.index("-o") + 1]
        assert str(i_val) == str(image_file)
        assert str(o_val) == str(image_file), "output path must equal input (in-place overwrite)"

    def test_case_2_off_skips_subprocess(
        self, image_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Case 2: WATERMARK_CLEAN=off → subprocess never called, returns path, file mtime unchanged."""
        from watermark_clean import clean_if_enabled

        monkeypatch.setenv("WATERMARK_CLEAN", "off")
        mtime_before = image_file.stat().st_mtime_ns
        with patch("watermark_clean.subprocess.run") as mock_run:
            result = clean_if_enabled(image_file)

        assert result == image_file
        assert mock_run.call_count == 0
        assert image_file.stat().st_mtime_ns == mtime_before

    def test_case_3_auto_retry_then_success(
        self, image_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Case 3: first subprocess call fails (non-zero), second succeeds → subprocess called twice, returns path."""
        from watermark_clean import clean_if_enabled

        monkeypatch.setenv("WATERMARK_CLEAN", "auto")
        rc_sequence = [_mock_run_rc(1), _mock_run_rc(0)]
        with patch("watermark_clean.shutil.which", return_value=r"C:\fake\cli.exe"):
            with patch("watermark_clean.subprocess.run", side_effect=rc_sequence) as mock_run:
                result = clean_if_enabled(image_file)

        assert result == image_file
        assert mock_run.call_count == 2

    def test_case_4_auto_both_fail_is_fail_soft(
        self,
        image_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Case 4: both subprocess calls fail → warning on stderr, exactly 2 calls, returns path (fail-soft), file unchanged."""
        from watermark_clean import clean_if_enabled

        monkeypatch.setenv("WATERMARK_CLEAN", "auto")
        original_bytes = image_file.read_bytes()
        with patch("watermark_clean.shutil.which", return_value=r"C:\fake\cli.exe"):
            with patch(
                "watermark_clean.subprocess.run",
                side_effect=[_mock_run_rc(1), _mock_run_rc(2)],
            ) as mock_run:
                result = clean_if_enabled(image_file)

        assert result == image_file
        assert mock_run.call_count == 2
        assert image_file.read_bytes() == original_bytes
        captured = capsys.readouterr()
        assert "[watermark_clean]" in captured.err

    def test_case_5_missing_path_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Case 5: path does not exist → raises FileNotFoundError."""
        from watermark_clean import clean_if_enabled

        monkeypatch.setenv("WATERMARK_CLEAN", "auto")
        missing = tmp_path / "nope.png"
        with pytest.raises(FileNotFoundError):
            clean_if_enabled(missing)

    def test_case_6_binary_missing_is_fail_soft(
        self,
        image_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Case 6: shutil.which returns None → warning logged, subprocess never called, returns path."""
        from watermark_clean import clean_if_enabled

        monkeypatch.setenv("WATERMARK_CLEAN", "auto")
        with patch("watermark_clean.shutil.which", return_value=None):
            with patch("watermark_clean.subprocess.run") as mock_run:
                result = clean_if_enabled(image_file)

        assert result == image_file
        assert mock_run.call_count == 0
        captured = capsys.readouterr()
        assert "[watermark_clean]" in captured.err
