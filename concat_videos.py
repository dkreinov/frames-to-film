#!/usr/bin/env python3
"""Stitch all OK segment videos into one movie (concat, no re-encode = best quality)."""
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile

_RUN_LOCK = threading.Lock()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(SCRIPT_DIR, "kling_test")
VID_DIR = os.path.join(IMG_DIR, "videos")
OUTPUT_FILE = os.path.join(VID_DIR, "full_movie.mp4")
TOOLS_DIR = os.path.join(SCRIPT_DIR, "tools")
FFMPEG_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)


def _part_sort_key(part: str):
    """Order '33' < '33_b' < '34' to match generate_all_videos image sequence."""
    m = re.match(r"^(\d+)(_([a-z]))?$", part)
    if m:
        return (int(m.group(1)), m.group(3) or "")
    return (9999, part)


def _pair_sort_key(key: str):
    """Sort key like '33_to_33_b' by (left_part, right_part)."""
    a, _, b = key.partition("_to_")
    return (_part_sort_key(a), _part_sort_key(b))


def _image_sort_key(filename: str):
    """Order image filenames like 1.png, 2.png, 33_b.png to match generate_all_videos."""
    base = filename.split(".")[0]
    return _part_sort_key(base)


def _ordered_segment_files():
    """Yield segment filenames in timeline order (1_to_2, 2_to_3, 3_to_4, ...), only if file exists."""
    image_files = [
        f for f in os.listdir(IMG_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png")) and re.match(r"^\d+(_[a-z])?\.", f)
    ]
    image_files.sort(key=_image_sort_key)
    for i in range(len(image_files) - 1):
        a = image_files[i].split(".")[0]
        b = image_files[i + 1].split(".")[0]
        key = f"{a}_to_{b}"
        seg_name = f"seg_{key}.mp4"
        path = os.path.join(VID_DIR, seg_name)
        if os.path.isfile(path):
            yield seg_name


def ordered_segment_files_for_sequence(image_files, videos_dir):
    files = []
    for i in range(len(image_files) - 1):
        a = image_files[i].split(".")[0]
        b = image_files[i + 1].split(".")[0]
        seg_name = f"seg_{a}_to_{b}.mp4"
        path = os.path.join(videos_dir, seg_name)
        if os.path.isfile(path):
            files.append(seg_name)
    return files


def ordered_segment_files_for_pair_keys(pair_keys, videos_dir):
    files = []
    for pair_key in pair_keys:
        seg_name = f"seg_{pair_key}.mp4"
        path = os.path.join(videos_dir, seg_name)
        if os.path.isfile(path):
            files.append(seg_name)
    return files


def _get_ffmpeg_exe():
    """Return path to ffmpeg: PATH, then tools/ffmpeg.exe, or download portable on Windows."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    local = os.path.join(TOOLS_DIR, "ffmpeg.exe")
    if os.path.isfile(local):
        return local
    if sys.platform != "win32":
        return None
    os.makedirs(TOOLS_DIR, exist_ok=True)
    zip_path = os.path.join(TOOLS_DIR, "ffmpeg.zip")
    print("Downloading portable ffmpeg...")
    try:
        urllib.request.urlretrieve(FFMPEG_URL, zip_path)
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        return None
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(TOOLS_DIR)
    for root, _, names in os.walk(TOOLS_DIR):
        if "ffmpeg.exe" in names:
            src = os.path.join(root, "ffmpeg.exe")
            if src != local:
                shutil.move(src, local)
            break
    try:
        os.remove(zip_path)
    except OSError:
        pass
    # Remove extracted top-level folder (e.g. ffmpeg-master-...)
    for name in os.listdir(TOOLS_DIR):
        path = os.path.join(TOOLS_DIR, name)
        if name != "ffmpeg.exe" and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            break
    return local if os.path.isfile(local) else None


def main():
    files = list(_ordered_segment_files())
    if not files:
        print("No segment files found (seg_*_to_*.mp4 in video dir, in image sequence order).")
        return
    list_path = os.path.join(VID_DIR, "concat_list.txt")
    with open(list_path, "w") as f:
        for name in files:
            # Path relative to list file so ffmpeg finds them
            f.write(f"file '{name}'\n")
    print(f"Concat list: {len(files)} segments -> {OUTPUT_FILE}")
    ffmpeg_exe = _get_ffmpeg_exe()
    if not ffmpeg_exe:
        print("ffmpeg not found and auto-download failed. Install ffmpeg and run again.", file=sys.stderr)
        print(f"  cd {VID_DIR}")
        print(f"  ffmpeg -y -f concat -safe 0 -i concat_list.txt -c copy full_movie.mp4")
        raise RuntimeError("ffmpeg not found and auto-download failed")
    cmd = [
        ffmpeg_exe, "-y", "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        OUTPUT_FILE,
    ]
    subprocess.run(cmd, check=True, cwd=VID_DIR)
    print(f"Done: {OUTPUT_FILE}")


def stitch_sequence(image_files, videos_dir, output_file):
    files = ordered_segment_files_for_sequence(image_files, videos_dir)
    if not files:
        raise RuntimeError("No matching segment files exist for the selected sequence.")

    os.makedirs(videos_dir, exist_ok=True)
    list_path = os.path.join(videos_dir, "concat_list.txt")
    with open(list_path, "w") as f:
        for name in files:
            f.write(f"file '{name}'\n")

    ffmpeg_exe = _get_ffmpeg_exe()
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg not found and auto-download failed.")

    cmd = [
        ffmpeg_exe, "-y", "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_file,
    ]
    subprocess.run(cmd, check=True, cwd=videos_dir)
    return {"segments": files, "output_file": output_file}


def stitch_pair_keys(pair_keys, videos_dir, output_file):
    files = ordered_segment_files_for_pair_keys(pair_keys, videos_dir)
    if not files:
        raise RuntimeError("No matching segment files exist for the selected transitions.")

    os.makedirs(videos_dir, exist_ok=True)
    list_path = os.path.join(videos_dir, "concat_list.txt")
    with open(list_path, "w") as f:
        for name in files:
            f.write(f"file '{name}'\n")

    ffmpeg_exe = _get_ffmpeg_exe()
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg not found and auto-download failed.")

    cmd = [
        ffmpeg_exe, "-y", "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_file,
    ]
    subprocess.run(cmd, check=True, cwd=videos_dir)
    return {"segments": files, "output_file": output_file}


def run(img_dir=None, video_dir=None, output_file=None):
    """Programmatic entry point used by the FastAPI backend.

    Swaps module-level IMG_DIR/VID_DIR/OUTPUT_FILE for the call and
    restores them after, so main() and CLI behavior remain unchanged.

    Serialised by _RUN_LOCK so concurrent FastAPI api-mode jobs can't
    race on the module globals.
    """
    global IMG_DIR, VID_DIR, OUTPUT_FILE
    with _RUN_LOCK:
        prev = (IMG_DIR, VID_DIR, OUTPUT_FILE)
        try:
            if img_dir is not None:
                IMG_DIR = str(img_dir)
            if video_dir is not None:
                VID_DIR = str(video_dir)
                OUTPUT_FILE = os.path.join(VID_DIR, "full_movie.mp4")
            if output_file is not None:
                OUTPUT_FILE = str(output_file)
            main()
        finally:
            IMG_DIR, VID_DIR, OUTPUT_FILE = prev


if __name__ == "__main__":
    main()
