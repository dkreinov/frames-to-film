"""Prove that the pipeline scripts raise RuntimeError (not SystemExit)
on missing env/tools, so the FastAPI job runner can catch via
`except Exception`.

Context: Phase 2 execution log flagged two api-mode blockers — this
test suite pins down the fixes.
"""
from __future__ import annotations

import pytest


def test_outpaint_images_get_client_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("gemini", raising=False)
    monkeypatch.delenv("GEMINI", raising=False)
    import outpaint_images
    with pytest.raises(RuntimeError):
        outpaint_images.get_client()


def test_outpaint_16_9_get_client_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("gemini", raising=False)
    monkeypatch.delenv("GEMINI", raising=False)
    import outpaint_16_9
    with pytest.raises(RuntimeError):
        outpaint_16_9.get_client()


def test_generate_get_jwt_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_jwt with missing Kling creds must raise RuntimeError, not SystemExit."""
    import generate_all_videos
    monkeypatch.setattr(generate_all_videos, "get_kling_credentials", lambda: (None, None))
    with pytest.raises(RuntimeError):
        generate_all_videos.get_jwt()


def test_concat_videos_missing_ffmpeg_raises_runtime_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """concat_videos.main with ffmpeg missing must raise RuntimeError, not SystemExit."""
    import concat_videos
    monkeypatch.setattr(concat_videos, "_get_ffmpeg_exe", lambda: None)
    monkeypatch.setattr(concat_videos, "IMG_DIR", str(tmp_path / "imgs"))
    monkeypatch.setattr(concat_videos, "VID_DIR", str(tmp_path / "vids"))
    monkeypatch.setattr(concat_videos, "OUTPUT_FILE", str(tmp_path / "vids" / "full_movie.mp4"))
    (tmp_path / "imgs").mkdir()
    (tmp_path / "vids").mkdir()
    # seed a minimal image sequence + fake segment so main reaches the ffmpeg check
    for n in (1, 2):
        (tmp_path / "imgs" / f"{n}.jpg").write_bytes(b"\xff\xd8\xff\xe0")
        (tmp_path / "vids" / f"seg_{n}_to_{n+1}.mp4").write_bytes(b"\x00" * 100)
    with pytest.raises(RuntimeError):
        concat_videos.main()
