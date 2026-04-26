"""Pure helper — builds an ffmpeg filter_complex string for xfade transitions.

No I/O, no subprocess. Caller is responsible for probing clip durations
and invoking ffmpeg with the returned filter_complex.

Contract:
    filter_complex, output_label, total_duration = build_xfade_filter_graph(
        segments=[
            {"path": Path("seg_1_to_2.mp4"), "duration_s": 5.0, "device_id": "cross_dissolve"},
            {"path": Path("seg_2_to_3.mp4"), "duration_s": 5.0, "device_id": None},  # last seg has no device
        ],
        devices={...},  # parsed cinematic_devices.yaml as {id: entry_dict}
    )

The segments list has N entries for N clips. The device_id on segment i is the
transition BETWEEN clip i-1 and clip i (so segments[0].device_id is ignored).

Empty ffmpeg_xfade ("") → hard cut via concat filter (no overlap).
Unknown device_id → default_xfade_flag with default_xfade_duration_s.
Single segment → passthrough [0:v]copy[vout].
"""
from __future__ import annotations

from pathlib import Path


def build_xfade_filter_graph(
    *,
    segments: list[dict],
    devices: dict,
    default_xfade_flag: str = "fade",
    default_xfade_duration_s: float = 0.5,
) -> tuple[str, str, float]:
    """Build ffmpeg filter_complex for N segments with N-1 transitions.

    Returns:
        filter_complex: str  — value for ffmpeg -filter_complex
        output_label:   str  — e.g. "[vout]", the final video stream label
        total_duration: float — expected output duration in seconds
    """
    n = len(segments)

    if n == 0:
        raise ValueError("segments must not be empty")

    if n == 1:
        return "[0:v]copy[vout]", "[vout]", segments[0]["duration_s"]

    parts: list[str] = []
    # acc_label tracks the label of the accumulated stream so far.
    # After joining clips 0..i it is written as f"[v{i}]".
    acc_label = "[0:v]"
    acc_duration = segments[0]["duration_s"]

    for i in range(1, n):
        seg = segments[i]
        device_id = seg.get("device_id") or ""
        seg_dur = seg["duration_s"]
        clip_label = f"[{i}:v]"

        # Resolve device
        device = devices.get(device_id)
        if device is None:
            xfade_flag = default_xfade_flag
            xfade_dur = default_xfade_duration_s
        else:
            xfade_flag = device.get("ffmpeg_xfade", "")
            xfade_dur = float(device.get("xfade_duration_s", 0.0))

        out_label = f"[v{i}]" if i < n - 1 else "[vout]"

        if xfade_flag:
            # xfade: clips overlap by xfade_dur
            offset = acc_duration - xfade_dur
            # Format duration: strip trailing zeros for cleaner strings
            dur_str = f"{xfade_dur:g}"
            off_str = f"{offset:g}"
            parts.append(
                f"{acc_label}{clip_label}xfade=transition={xfade_flag}"
                f":duration={dur_str}:offset={off_str}{out_label}"
            )
            acc_duration = acc_duration + seg_dur - xfade_dur
        else:
            # Hard cut: no overlap; use concat filter
            parts.append(
                f"{acc_label}{clip_label}concat=n=2:v=1:a=0{out_label}"
            )
            acc_duration = acc_duration + seg_dur

        acc_label = out_label

    filter_complex = ";".join(parts)
    return filter_complex, "[vout]", acc_duration
