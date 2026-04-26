"""Stitch stage service — ffmpeg concat or xfade-aware stitching.

When metadata/story.json is present, applies per-pair cinematic-device
transitions via ffmpeg xfade filter_complex. Falls back to stream-copy
concat (concat_videos.run) when story.json is absent.

The `mode` param is accepted for signature symmetry with prepare/extend/
generate but only gates the post-stitch judges, not the stitch itself.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from backend.services.judges import orchestrator as judges_orch
from backend.services.project_schema import (
    CLIPS_DIRNAME,
    CLIPS_RAW_DIRNAME,
    EXTENDED_DIRNAME,
    FINAL_DIRNAME,
    METADATA_DIRNAME,
)
from backend.services.stitch_xfade import build_xfade_filter_graph

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEVICES_PATH = _REPO_ROOT / "data" / "cinematic_devices.yaml"
_FALLBACK_DEVICE = "cross_dissolve"
_DEFAULT_CLIP_DURATION_S = 5.0


def _load_devices() -> dict:
    """Load cinematic_devices.yaml as {device_id: entry_dict}."""
    if not _DEVICES_PATH.is_file():
        return {}
    entries = yaml.safe_load(_DEVICES_PATH.read_text(encoding="utf-8")) or []
    return {e["id"]: e for e in entries if "id" in e}


def _probe_duration(seg_path: Path, ffmpeg_exe: str) -> float:
    """Return clip duration seconds via ffprobe; fallback to 5.0s on failure."""
    ffprobe = Path(ffmpeg_exe).with_name(
        "ffprobe.exe" if Path(ffmpeg_exe).name.endswith(".exe") else "ffprobe"
    )
    if not ffprobe.is_file():
        return _DEFAULT_CLIP_DURATION_S
    try:
        result = subprocess.run(
            [str(ffprobe), "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(seg_path)],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return _DEFAULT_CLIP_DURATION_S


def _stitch_with_xfade(
    segments: list[Path],
    story_pair_intents: list[dict],
    output_file: Path,
    ffmpeg_exe: str,
) -> None:
    """Build filter_complex and invoke ffmpeg xfade for the given segments."""
    devices = _load_devices()

    seg_dicts: list[dict] = []
    for i, seg in enumerate(segments):
        duration = _probe_duration(seg, ffmpeg_exe)
        # device_id for transition INTO this segment (none for first)
        if i == 0:
            device_id = None
        elif i - 1 < len(story_pair_intents):
            device_id = story_pair_intents[i - 1].get("device", _FALLBACK_DEVICE)
        else:
            device_id = _FALLBACK_DEVICE
        seg_dicts.append({"path": seg, "duration_s": duration, "device_id": device_id})

    filter_complex, out_label, _ = build_xfade_filter_graph(
        segments=seg_dicts, devices=devices
    )

    cmd = [ffmpeg_exe, "-y"]
    for seg in segments:
        cmd += ["-i", str(seg)]
    cmd += ["-filter_complex", filter_complex, "-map", out_label, "-an", str(output_file)]
    subprocess.run(cmd, check=True)


def run_stitch(project_dir: Path, mode: str | None = None) -> dict:
    project_dir = Path(project_dir)
    img_dir = project_dir / EXTENDED_DIRNAME
    video_dir = project_dir / CLIPS_DIRNAME / CLIPS_RAW_DIRNAME
    final_dir = project_dir / FINAL_DIRNAME
    final_dir.mkdir(parents=True, exist_ok=True)
    output_file = final_dir / "full_movie.mp4"

    if not video_dir.is_dir():
        raise FileNotFoundError(f"clips/raw dir missing (run generate first): {video_dir}")
    segments = sorted(video_dir.glob("seg_*_to_*.mp4"))
    if not segments:
        raise RuntimeError(f"no segments to stitch in {video_dir}")

    story_path = project_dir / METADATA_DIRNAME / "story.json"
    if story_path.is_file():
        story = json.loads(story_path.read_text(encoding="utf-8"))
        pair_intents = story.get("pair_intents", [])
        from concat_videos import _get_ffmpeg_exe
        ffmpeg_exe = _get_ffmpeg_exe()
        if ffmpeg_exe:
            _stitch_with_xfade(segments, pair_intents, output_file, ffmpeg_exe)
        else:
            # ffmpeg not found — fall back to concat
            from concat_videos import run as concat_run
            concat_run(img_dir=img_dir, video_dir=video_dir, output_file=output_file)
    else:
        from concat_videos import run as concat_run
        concat_run(img_dir=img_dir, video_dir=video_dir, output_file=output_file)

    # Phase 7.1 — score the stitched movie post-stitch (advisory).
    if mode != "mock" and judges_orch.is_enabled():
        try:
            judges_orch.run_post_stitch_judge(project_dir)
        except Exception as exc:
            print(f"[judges] post-stitch skipped: {exc!r}")

    return {"output_file": str(output_file), "segments": [s.name for s in segments]}


def stitch_runner(**payload) -> dict:
    return run_stitch(
        project_dir=Path(payload["project_dir"]),
        mode=payload.get("mode"),
    )
