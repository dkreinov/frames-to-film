from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
from io import BytesIO
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image, ImageChops, ImageOps, ImageStat

from concat_videos import ordered_segment_files_for_sequence, stitch_sequence
from extend_image_judge import judge_available as local_judge_available
from extend_image_judge import judge_extension as run_local_extension_judge
from generate_all_videos import build_pairs_from_sequence, generate_pairs_for_sequence, sort_key as natural_image_sort_key
from image_pair_prompts import FALLBACK_PROMPT, PAIR_PROMPTS
from outpaint_16_9 import TARGET_ASPECT_RATIO, choose_extension_prompt
from redo_runner import (
    generate_automatic_retry_prompt,
    preview_redo_queue,
    redo_request_key,
    run_redo_queue,
)
from review_models import DECISIONS, ISSUE_TAGS, RedoRequest, ReviewRecord
from review_store import (
    accept_review_version,
    DEFAULT_RUN_ID,
    discover_clip_pairs,
    ensure_review_files,
    frame_image_path,
    load_redo_queue,
    load_reviews,
    load_winners,
    queue_redo,
    remove_redo_request,
    remove_redo_waiting_review,
    save_review,
    set_redo_prompt_override,
    save_winner,
)


DECISION_LABELS = {
    "approve": "Approve",
    "redo": "Redo",
    "needs_discussion": "Needs discussion",
}

ISSUE_LABELS = {
    "face_bad": "Face looks bad",
    "identity_drift": "Identity drift",
    "hands_body_bad": "Hands or body look wrong",
    "transition_bad": "Transition is bad",
    "scenario_wrong": "Scenario is wrong",
    "background_wrong": "Background is wrong",
    "style_mismatch": "Style mismatch",
    "too_fast": "Too fast",
    "too_slow": "Too slow",
    "artifacts": "Artifacts",
    "emotion_wrong": "Emotion is wrong",
    "prompt_ignored": "Prompt ignored",
}

ISSUE_GROUPS = [
    ("Face and identity", ["face_bad", "identity_drift", "hands_body_bad", "emotion_wrong"]),
    ("Transition and motion", ["transition_bad", "too_fast", "too_slow"]),
    ("Scene and style", ["scenario_wrong", "background_wrong", "style_mismatch", "prompt_ignored", "artifacts"]),
]

STATUS_LABELS = {
    "Needs review": "Unreviewed",
    "Redo queued": "Needs redo",
    "Approved": "Approved",
    "Needs discussion": "Needs discussion",
    "waiting_review": "New version ready",
    "queued": "Queued to rerun",
    "failed": "Retry failed",
}

STATUS_FILTERS = [
    "All clips",
    "Rebuilt clips",
    "Needs review",
    "Redo queue",
    "Approved",
    "Needs discussion",
]

FILTER_LABELS = {
    "All clips": "All clips",
    "Rebuilt clips": "Rebuilt clips",
    "Needs review": "Unreviewed",
    "Redo queue": "Needs redo",
    "Approved": "Approved",
    "Needs discussion": "Needs discussion",
}

STATUS_SHORT_LABELS = {
    "Needs review": "[ ]",
    "Redo queued": "[R]",
    "Approved": "[OK]",
    "Needs discussion": "[?]",
}

ROOT_DIR = Path(__file__).resolve().parent
OUTPAINTED_DIR = ROOT_DIR / "outpainted"
RAW_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
DEFAULT_EXTENSION_OUTPUT_DIR = "kling_test/manual_extends"
EXTEND_TAB_STATE_PATH = ROOT_DIR / "pipeline_runs" / "extend_tab_state.json"
BUILD_TAB_STATE_PATH = ROOT_DIR / "pipeline_runs" / "build_movie_state.json"
EXTEND_TARGET_W = 5376
EXTEND_TARGET_H = 3024
EXTEND_IMAGE_MODEL = "gemini-3-pro-image-preview"
STORYBOARD_COMPONENT = components.declare_component(
    "movie_storyboard",
    path=str(ROOT_DIR / "components" / "storyboard"),
)


def main() -> None:
    st.set_page_config(
        page_title="Olga Movie Review",
        page_icon="M",
        layout="wide",
    )
    inject_styles()

    st.markdown(
        """
        <div class="hero-banner">
            <h1>Olga Movie Review</h1>
            <p>Review clips, compare rebuilt versions, and queue smarter retries without losing story continuity.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    review_notice = st.session_state.pop("review_notice", "")
    if review_notice:
        st.success(review_notice)

    run_id, status_filter = sidebar_controls()
    ensure_review_files(run_id)

    pairs = discover_clip_pairs()
    reviews = load_reviews(run_id)
    redo_requests = load_redo_queue(run_id)
    winners = load_winners(run_id)

    if not pairs:
        st.error("No generated clips were found in kling_test/videos.")
        return

    review_lookup = {(item.pair_id, item.version): item for item in reviews}
    queued_redo_lookup = {
        (item.pair_id, item.source_version): item
        for item in redo_requests
        if item.status == "queued"
    }
    waiting_review_lookup = {
        (item.pair_id, item.target_version): item
        for item in redo_requests
        if item.status == "waiting_review" and item.target_version is not None
    }
    pair_rows = build_pair_rows(pairs, review_lookup, queued_redo_lookup, winners)

    selected_pair = select_pair(pairs, pair_rows, status_filter)

    extend_tab, build_tab, review_tab, queue_tab = st.tabs(["Extend images", "Build movie", "Review", "Redo queue"])
    with extend_tab:
        render_extend_images_tab()

    with build_tab:
        render_build_movie_tab()

    with review_tab:
        render_review_panel(
            selected_pair,
            review_lookup,
            queued_redo_lookup,
            waiting_review_lookup,
            winners,
            run_id,
            pair_rows,
            progress_counts(pair_rows),
            status_filter,
        )
        with st.expander("Inbox overview", expanded=False):
            render_inbox(pair_rows, status_filter, selected_pair.pair_id)

    with queue_tab:
        render_redo_queue(redo_requests, review_lookup, winners, run_id)

    error_message = st.session_state.pop("redo_run_error", "")
    if error_message:
        st.error(error_message)


@st.cache_data
def discover_image_folders() -> list[Path]:
    excluded = {".git", ".streamlit", "_cursor", "__pycache__", "pipeline_runs", "docs", "tools"}
    folders: list[Path] = []
    for path in [ROOT_DIR] + sorted(
        [
            candidate
            for candidate in ROOT_DIR.rglob("*")
            if candidate.is_dir() and not any(part in excluded for part in candidate.parts)
        ],
        key=lambda item: str(item).lower(),
    ):
        try:
            has_images = any(
                child.is_file() and child.suffix.lower() in RAW_IMAGE_EXTENSIONS
                for child in path.iterdir()
            )
        except OSError:
            continue
        if has_images:
            folders.append(path)
    return folders


def discover_extension_sources(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        return []
    return sorted(
        [
            path
            for path in source_dir.iterdir()
            if path.is_file() and path.suffix.lower() in RAW_IMAGE_EXTENSIONS
        ],
        key=lambda path: path.name.lower(),
    )


def discover_orderable_images(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        return []
    return sorted(
        [
            path
            for path in source_dir.iterdir()
            if path.is_file() and path.suffix.lower() in RAW_IMAGE_EXTENSIONS
        ],
        key=lambda path: natural_image_sort_key(path.name),
    )


def normalize_ordered_images(saved_order: list[str], available_names: list[str]) -> list[str]:
    available_set = set(available_names)
    ordered = [name for name in saved_order if name in available_set]
    ordered.extend(name for name in available_names if name not in ordered)
    return ordered


def image_cache_key(path: Path) -> str:
    stats = path.stat()
    return f"{stats.st_mtime_ns}:{stats.st_size}"


@st.cache_data
def load_display_image_bytes(path_text: str, max_width: int, file_key: str) -> bytes:
    image = Image.open(path_text)
    image = ImageOps.exif_transpose(image)

    if image.width > max_width:
        scale = max_width / image.width
        new_height = max(1, int(image.height * scale))
        image = image.resize((max_width, new_height), Image.LANCZOS)

    buffer = BytesIO()
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


@st.cache_data
def load_compare_data_uri(path_text: str, max_width: int, file_key: str) -> str:
    data = load_display_image_bytes(path_text, max_width, file_key)
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def render_storyboard_component(
    items: list[dict[str, str]],
    selected_id: str,
    component_key: str,
) -> dict[str, list[str] | str] | None:
    return STORYBOARD_COMPONENT(
        items=items,
        selected_id=selected_id,
        key=component_key,
        default={"ordered_ids": [item["id"] for item in items], "selected_id": selected_id},
    )


def average_hash(image: Image.Image, size: int = 8) -> int:
    gray = image.convert("L").resize((size, size), Image.LANCZOS)
    pixels = list(gray.getdata())
    average = sum(pixels) / len(pixels)
    bits = 0
    for value in pixels:
        bits = (bits << 1) | int(value >= average)
    return bits


@st.cache_data
def face_preservation_judge(
    source_path_text: str,
    source_file_key: str,
    target_path_text: str,
    target_file_key: str,
) -> dict[str, float | str]:
    source_image = ImageOps.exif_transpose(Image.open(source_path_text)).convert("RGB")
    target_image = ImageOps.exif_transpose(Image.open(target_path_text)).convert("RGB")

    target_height = target_image.height
    resized_width = max(1, round(source_image.width * target_height / source_image.height))
    source_resized = source_image.resize((resized_width, target_height), Image.LANCZOS)

    if resized_width >= target_image.width:
        source_resized = source_image.resize((target_image.width, round(source_image.height * target_image.width / source_image.width)), Image.LANCZOS)
        crop_top = max(0, (source_resized.height - target_image.height) // 2)
        source_resized = source_resized.crop((0, crop_top, target_image.width, crop_top + target_image.height))
        target_center = target_image
    else:
        crop_left = (target_image.width - resized_width) // 2
        target_center = target_image.crop((crop_left, 0, crop_left + resized_width, target_height))

    width, height = source_resized.size
    face_box = (
        int(width * 0.14),
        int(height * 0.06),
        int(width * 0.86),
        int(height * 0.60),
    )
    source_face = source_resized.crop(face_box)
    target_face = target_center.crop(face_box)

    face_diff = ImageChops.difference(source_face, target_face)
    face_rms = sum(ImageStat.Stat(face_diff).rms) / 3
    face_hash_distance = bin(average_hash(source_face) ^ average_hash(target_face)).count("1") / 64

    center_diff = ImageChops.difference(source_resized, target_center)
    center_rms = sum(ImageStat.Stat(center_diff).rms) / 3

    face_score = (face_rms / 255) * 0.65 + face_hash_distance * 0.35
    center_score = center_rms / 255
    total_score = face_score * 0.75 + center_score * 0.25

    if total_score <= 0.12:
        label = "Likely preserved"
    elif total_score <= 0.2:
        label = "Possible drift"
    else:
        label = "Likely changed"

    return {
        "label": label,
        "score": round(total_score, 3),
        "face_score": round(face_score, 3),
        "center_score": round(center_score, 3),
    }


def resolve_extension_output_dir(folder_text: str) -> Path | None:
    folder_text = folder_text.strip().replace("\\", "/")
    if not folder_text:
        folder_text = DEFAULT_EXTENSION_OUTPUT_DIR
    relative_path = Path(folder_text)
    if relative_path.is_absolute():
        return relative_path

    return (ROOT_DIR / relative_path).resolve()


def extension_target_path(source_path: Path, output_dir: Path) -> Path:
    return output_dir / source_path.name


def extension_target_variants(source_path: Path, output_dir: Path) -> list[Path]:
    base_path = extension_target_path(source_path, output_dir)
    variants: list[Path] = []
    if base_path.exists():
        variants.append(base_path)

    stem = source_path.stem
    suffix = source_path.suffix
    pattern = f"{stem}_v*{suffix}"
    numbered: list[tuple[int, Path]] = []
    for candidate in sorted(output_dir.glob(pattern), key=lambda path: path.name.lower()):
        suffix_text = candidate.stem.removeprefix(f"{stem}_v")
        if suffix_text.isdigit():
            numbered.append((int(suffix_text), candidate))
    numbered.sort(key=lambda item: item[0])
    variants.extend(path for _, path in numbered)
    return variants


def next_extension_target_path(source_path: Path, output_dir: Path) -> Path:
    variants = extension_target_variants(source_path, output_dir)
    if not variants:
        return extension_target_path(source_path, output_dir)
    last_variant = variants[-1]
    stem = source_path.stem
    suffix = source_path.suffix
    if last_variant.name == source_path.name:
        next_version = 2
    else:
        suffix_text = last_variant.stem.removeprefix(f"{stem}_v")
        next_version = int(suffix_text) + 1 if suffix_text.isdigit() else 2
    return output_dir / f"{stem}_v{next_version}{suffix}"


def relative_folder_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR.resolve())) if path.resolve() != ROOT_DIR.resolve() else "."
    except ValueError:
        return str(path)


def folder_key_text(path: Path) -> str:
    return str(path).replace("\\", "/")


def path_from_saved_text(path_text: str) -> Path:
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate
    return (ROOT_DIR / candidate).resolve()


def load_extend_tab_state() -> dict[str, str | bool]:
    if not EXTEND_TAB_STATE_PATH.exists():
        return {}
    try:
        return json.loads(EXTEND_TAB_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_build_tab_state() -> dict[str, str | bool | list[str]]:
    if not BUILD_TAB_STATE_PATH.exists():
        return {}
    try:
        return json.loads(BUILD_TAB_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_build_tab_state(
    source_folder: Path,
    ordered_images: list[str],
    selected_pair_keys: list[str],
    custom_order: bool,
    pool_folder: Path | None = None,
) -> None:
    BUILD_TAB_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_folder": relative_folder_label(source_folder),
        "ordered_images": ordered_images,
        "selected_pair_keys": selected_pair_keys,
        "custom_order": custom_order,
    }
    if pool_folder is not None:
        payload["pool_folder"] = relative_folder_label(pool_folder)
    BUILD_TAB_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_extend_tab_state(
    source_folder: Path,
    output_folder: str,
    only_missing: bool,
    active_image: str,
    swap_compare_sides: bool,
    local_judge_enabled: bool,
) -> None:
    EXTEND_TAB_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_folder": relative_folder_label(source_folder),
        "output_folder": output_folder,
        "only_missing": only_missing,
        "active_image": active_image,
        "swap_compare_sides": swap_compare_sides,
        "local_judge_enabled": local_judge_enabled,
    }
    EXTEND_TAB_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def open_folder_in_windows(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    os.startfile(str(path))


def browse_for_folder(initial_dir: Path) -> Path | None:
    initial = initial_dir if initial_dir.exists() else ROOT_DIR
    python_script = """
import sys
import tkinter as tk
from tkinter import filedialog

initial = sys.argv[1]
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
selected = filedialog.askdirectory(initialdir=initial)
root.destroy()
if selected:
    print(selected)
""".strip()
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                python_script,
                str(initial),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        selected = (result.stdout or "").strip()
        if selected:
            return Path(selected)
    except OSError:
        pass

    escaped_initial = str(initial).replace("'", "''")
    powershell_script = f"""
$shell = New-Object -ComObject Shell.Application
$folder = $shell.BrowseForFolder(0, 'Select folder', 0, '{escaped_initial}')
if ($folder) {{
    Write-Output $folder.Self.Path
}}
""".strip()
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-STA",
                "-Command",
                powershell_script,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        selected = (result.stdout or "").strip()
        if selected:
            return Path(selected)
    except OSError:
        pass

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory(initialdir=str(initial))
    root.destroy()
    if not selected:
        return None
    return Path(selected)


@st.cache_data
def extension_prompt_for_image(path_text: str, file_key: str) -> tuple[str, str, float, float]:
    source_path = Path(path_text)
    with Image.open(path_text) as source_image:
        source_image = ImageOps.exif_transpose(source_image)
        prompt, profile = choose_extension_prompt(source_image, source_path.name)
        aspect_ratio = source_image.width / source_image.height
        width_multiplier = TARGET_ASPECT_RATIO / aspect_ratio
    return prompt, profile, aspect_ratio, width_multiplier


def save_uploaded_extension(uploaded_file, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(uploaded_file)
    if target_path.suffix.lower() == ".png":
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        image.save(target_path, format="PNG")
        return

    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(target_path, format="JPEG", quality=95)


def get_extend_api_client() -> genai.Client:
    load_dotenv(ROOT_DIR / ".env")
    api_key = os.getenv("gemini")
    if not api_key:
        raise RuntimeError("No 'gemini' key found in .env")
    return genai.Client(api_key=api_key)


def upscale_extend_result(image: Image.Image) -> Image.Image:
    width, height = image.size
    if width >= EXTEND_TARGET_W and height >= EXTEND_TARGET_H:
        return image.resize((EXTEND_TARGET_W, EXTEND_TARGET_H), Image.LANCZOS)

    scale = max(EXTEND_TARGET_W / width, EXTEND_TARGET_H / height)
    resized_width = int(width * scale)
    resized_height = int(height * scale)
    resized = image.resize((resized_width, resized_height), Image.LANCZOS)
    left = (resized_width - EXTEND_TARGET_W) // 2
    top = (resized_height - EXTEND_TARGET_H) // 2
    return resized.crop((left, top, left + EXTEND_TARGET_W, top + EXTEND_TARGET_H))


def run_extend_image_api(source_path: Path, target_path: Path, prompt: str) -> None:
    source_image = Image.open(source_path)
    source_image = ImageOps.exif_transpose(source_image)
    if source_image.mode != "RGB":
        source_image = source_image.convert("RGB")

    buffer = BytesIO()
    source_image.save(buffer, format="JPEG", quality=95)
    buffer.seek(0)
    image_for_api = Image.open(buffer)

    client = get_extend_api_client()
    response = client.models.generate_content(
        model=EXTEND_IMAGE_MODEL,
        contents=[prompt, image_for_api],
        config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
    )

    result_image = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            result_image = Image.open(BytesIO(part.inline_data.data))
            break

    if result_image is None:
        raise RuntimeError("Gemini API returned no image result.")

    if result_image.mode != "RGB":
        result_image = result_image.convert("RGB")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    upscale_extend_result(result_image).save(target_path, format="JPEG", quality=95)


def run_ai_face_judge(source_path: Path, target_path: Path) -> dict[str, str | int]:
    source_image = ImageOps.exif_transpose(Image.open(source_path)).convert("RGB")
    target_image = ImageOps.exif_transpose(Image.open(target_path)).convert("RGB")
    client = get_extend_api_client()
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            """
Compare the original photo and the extended photo.
Treat the original photo as ground truth.
Focus only on whether any people changed in a bad way in the extended photo.

Check for:
- changed face or identity
- scary or uncanny face
- duplicated or cloned person
- altered pose, body, arms, hands, or clothing
- invented extra people near the edges

Important rules:
- If the extended photo shows more people than the original, verdict must be fail.
- If a person appears duplicated at the left or right edge, verdict must be fail.
- If any face looks uncanny, scary, warped, or clearly different from the original, verdict must be fail.
- Use warning only for mild uncertainty.
- Use pass only when the same people are preserved cleanly.

Return strict JSON with this shape:
{"verdict":"pass|warning|fail","score":0-100,"reason":"short plain sentence"}
""".strip(),
            source_image,
            target_image,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    text = response.text.strip()
    result = json.loads(text)
    return {
        "verdict": str(result.get("verdict", "warning")),
        "score": int(result.get("score", 0)),
        "reason": str(result.get("reason", "")).strip(),
    }


def render_overlay_image_compare(
    source_path: Path,
    target_path: Path,
    large_view: bool,
    swap_sides: bool,
) -> None:
    source_uri = load_compare_data_uri(
        str(source_path),
        2200 if large_view else 1500,
        image_cache_key(source_path),
    )
    target_uri = load_compare_data_uri(
        str(target_path),
        2200 if large_view else 1500,
        image_cache_key(target_path),
    )
    left_uri = target_uri if swap_sides else source_uri
    right_uri = source_uri if swap_sides else target_uri
    left_label = "Extended" if swap_sides else "Original"
    right_label = "Original" if swap_sides else "Extended"
    height = 920 if large_view else 620
    script = f"""
    <style>
      .extend-compare {{
        background: #17120f;
        border-radius: 18px;
        overflow: hidden;
        position: relative;
      }}
      .extend-compare__stage {{
        aspect-ratio: 16 / 9;
        position: relative;
        width: 100%;
      }}
      .extend-compare__stage img {{
        height: 100%;
        inset: 0;
        object-fit: contain;
        position: absolute;
        width: 100%;
      }}
      .extend-compare__before {{
        clip-path: inset(0 calc(100% - var(--split, 50%)) 0 0);
      }}
      .extend-compare__line {{
        background: rgba(255,255,255,0.95);
        box-shadow: 0 0 0 1px rgba(0,0,0,0.18);
        height: 100%;
        left: var(--split, 50%);
        position: absolute;
        top: 0;
        width: 3px;
      }}
      .extend-compare__label {{
        background: rgba(15, 23, 42, 0.74);
        border-radius: 999px;
        color: #fff7ed;
        font: 600 13px/1 system-ui, sans-serif;
        left: 14px;
        padding: 8px 12px;
        position: absolute;
        top: 14px;
      }}
      .extend-compare__label--after {{
        left: auto;
        right: 14px;
      }}
      .extend-compare__controls {{
        align-items: center;
        display: flex;
        gap: 12px;
        padding: 12px 14px 14px;
      }}
      .extend-compare__controls input {{
        flex: 1;
      }}
    </style>
    <div class="extend-compare" id="extend-compare">
      <div class="extend-compare__stage" id="extend-stage" style="--split:50%">
        <img class="extend-compare__after" src="{right_uri}" alt="{right_label} image" />
        <img class="extend-compare__before" src="{left_uri}" alt="{left_label} image" />
        <div class="extend-compare__line"></div>
        <div class="extend-compare__label">{left_label}</div>
        <div class="extend-compare__label extend-compare__label--after">{right_label}</div>
      </div>
      <div class="extend-compare__controls">
        <span style="color:#f5e7d3;font:600 13px/1 system-ui,sans-serif;">Drag to compare</span>
        <input id="extend-slider" type="range" min="0" max="100" value="50" />
      </div>
    </div>
    <script>
      const stage = document.getElementById("extend-stage");
      const slider = document.getElementById("extend-slider");
      if (stage && slider) {{
        slider.addEventListener("input", () => {{
          stage.style.setProperty("--split", slider.value + "%");
        }});
      }}
    </script>
    """
    components.html(script, height=height)


def render_extend_scroll_restore(anchor_id: str) -> None:
    script = f"""
    <script>
      const anchorId = "{anchor_id}";
      function scrollToAnchor() {{
        const anchor = window.parent.document.getElementById(anchorId);
        if (anchor) {{
          const parentWindow = window.parent;
          const top = anchor.getBoundingClientRect().top + parentWindow.scrollY - 24;
          parentWindow.scrollTo({{top, behavior: "auto"}});
        }}
      }}
      let attempts = 0;
      function keepTrying() {{
        scrollToAnchor();
        attempts += 1;
        if (attempts < 18) {{
          window.setTimeout(keepTrying, 120);
        }}
      }}
      window.addEventListener("load", () => {{
        window.setTimeout(keepTrying, 80);
      }});
      window.setTimeout(keepTrying, 120);
    </script>
    """
    components.html(script, height=0)


def render_extension_compare(
    source_path: Path,
    target_path: Path,
    compare_mode: str,
    large_view: bool,
    swap_sides: bool,
) -> None:
    if compare_mode == "Overlay slider":
        render_overlay_image_compare(source_path, target_path, large_view, swap_sides)
        return

    source_image = load_display_image_bytes(
        str(source_path),
        2200 if large_view else 1500,
        image_cache_key(source_path),
    )
    target_image = load_display_image_bytes(
        str(target_path),
        2200 if large_view else 1500,
        image_cache_key(target_path),
    )
    left_image = target_image if swap_sides else source_image
    right_image = source_image if swap_sides else target_image
    left_caption = f"{'Extended' if swap_sides else 'Original'}: {target_path.name if swap_sides else source_path.name}"
    right_caption = f"{'Original' if swap_sides else 'Extended'}: {source_path.name if swap_sides else target_path.name}"

    if compare_mode == "Stacked":
        st.image(left_image, caption=left_caption, use_container_width=True)
        st.image(right_image, caption=right_caption, use_container_width=True)
        return

    compare_cols = st.columns(2, gap="large")
    with compare_cols[0]:
        st.image(left_image, caption=left_caption, use_container_width=True)
    with compare_cols[1]:
        st.image(right_image, caption=right_caption, use_container_width=True)


def render_extension_nav(
    visible_names: list[str],
    browser_rows: list[dict[str, str]],
    active_key: str,
    current_index: int,
    *,
    include_picker: bool,
) -> str:
    nav_cols = st.columns([1, 1, 1.2, 1.1, 2.0] if include_picker else [1, 1, 1.2, 1.2], gap="small")
    if nav_cols[0].button(
        "Previous image",
        use_container_width=True,
        disabled=current_index == 0,
        key=f"{active_key}::prev::{include_picker}",
    ):
        st.session_state["pending_extend_scroll_anchor"] = "extend-compare-anchor"
        st.session_state[active_key] = visible_names[current_index - 1]
        st.rerun()
    if nav_cols[1].button(
        "Next image",
        use_container_width=True,
        disabled=current_index == len(visible_names) - 1,
        key=f"{active_key}::next::{include_picker}",
    ):
        st.session_state["pending_extend_scroll_anchor"] = "extend-compare-anchor"
        st.session_state[active_key] = visible_names[current_index + 1]
        st.rerun()
    if nav_cols[2].button(
        "Next needs extension",
        use_container_width=True,
        key=f"{active_key}::pending::{include_picker}",
    ):
        pending_names = [
            row["image"]
            for row in browser_rows
            if row["status"] == "Needs extension" and row["image"] in visible_names
        ]
        if pending_names:
            st.session_state["pending_extend_scroll_anchor"] = "extend-compare-anchor"
            st.session_state[active_key] = pending_names[0]
            st.rerun()
    if include_picker and nav_cols[3].button(
        "Jump to compare",
        use_container_width=True,
        key=f"{active_key}::jump_compare",
    ):
        st.session_state["pending_extend_scroll_anchor"] = "extend-compare-anchor"
        st.rerun()
    if include_picker:
        selected_name = nav_cols[4].selectbox(
            "Active image",
            options=visible_names,
            index=visible_names.index(st.session_state[active_key]),
            label_visibility="collapsed",
        )
        st.session_state[active_key] = selected_name
        return selected_name

    nav_cols[3].caption("Use these buttons while comparing to move without scrolling up.")
    return st.session_state[active_key]


def render_extend_images_tab() -> None:
    st.subheader("Extend images")
    st.caption("Browse one image at a time, compare the original against the current saved extension, then upload a replacement if needed.")
    workflow = "16:9 from 4:3 images"
    saved_state = load_extend_tab_state()
    pending_source_folder = st.session_state.pop("pending_extend_source_folder", None)
    if pending_source_folder is not None:
        st.session_state["extend_source_folder"] = pending_source_folder
    pending_output_folder = st.session_state.pop("pending_extend_output_text", None)
    if pending_output_folder is not None:
        st.session_state["extend_output_text"] = pending_output_folder
    if "extend_local_judge_enabled" not in st.session_state:
        st.session_state["extend_local_judge_enabled"] = bool(saved_state.get("local_judge_enabled", False))

    image_folders = discover_image_folders()
    default_folder = OUTPAINTED_DIR
    folder_options = [path for path in image_folders if path.exists()]
    if default_folder not in folder_options:
        folder_options.insert(0, default_folder)
    initial_source_folder = path_from_saved_text(
        str(saved_state.get("source_folder", relative_folder_label(default_folder)))
    )
    if pending_source_folder is not None and pending_source_folder not in folder_options:
        folder_options.insert(0, pending_source_folder)
    if initial_source_folder not in folder_options:
        folder_options.insert(0, initial_source_folder)
    if "extend_source_folder" not in st.session_state or st.session_state["extend_source_folder"] not in folder_options:
        st.session_state["extend_source_folder"] = initial_source_folder
    output_preset_options = [DEFAULT_EXTENSION_OUTPUT_DIR]
    output_preset_options.extend(
        relative_folder_label(path)
        for path in folder_options
        if relative_folder_label(path) not in output_preset_options
    )
    output_preset_options.append("Custom...")

    output_preset_key = "extend_output_preset"
    output_text_key = "extend_output_text"
    initial_output_folder = str(saved_state.get("output_folder", DEFAULT_EXTENSION_OUTPUT_DIR))
    if output_preset_key not in st.session_state:
        st.session_state[output_preset_key] = (
            initial_output_folder if initial_output_folder in output_preset_options else "Custom..."
        )
    if output_text_key not in st.session_state:
        st.session_state[output_text_key] = initial_output_folder

    workspace_cols = st.columns(2, gap="large")
    with workspace_cols[0]:
        st.markdown("**Source folder**")
        source_cols = st.columns([1.55, 0.5, 0.45], gap="small")
        selected_folder = source_cols[0].selectbox(
            "Source folder",
            options=folder_options,
            key="extend_source_folder",
            format_func=relative_folder_label,
            label_visibility="collapsed",
            help="Choose which folder of images to browse.",
        )
        if source_cols[1].button("Browse...", use_container_width=True, key="browse_source_folder"):
            picked_source = browse_for_folder(selected_folder)
            if picked_source is not None:
                st.session_state["pending_extend_source_folder"] = picked_source
                st.rerun()
        if source_cols[2].button("Open", use_container_width=True, key="open_source_folder"):
            open_folder_in_windows(selected_folder)
        st.caption("Pick the folder you want to browse and compare.")

    with workspace_cols[1]:
        st.markdown("**Output folder**")
        preset_col, text_col = st.columns([0.95, 1.25], gap="small")
        selected_output_preset = preset_col.selectbox(
            "Output folder preset",
            options=output_preset_options,
            key=output_preset_key,
            label_visibility="collapsed",
            help="Pick an existing folder quickly, or switch to Custom and type any project-relative output path.",
        )
        if selected_output_preset != "Custom...":
            st.session_state[output_text_key] = selected_output_preset

        output_folder_text = text_col.text_input(
            "Output folder",
            key=output_text_key,
            label_visibility="collapsed",
            help="Images are treated as the same item only when the same filename already exists in this chosen output folder. You can type any relative project path here.",
        )
        output_action_cols = st.columns([0.55, 0.45, 1.2], gap="small")
        if output_action_cols[0].button("Browse...", use_container_width=True, key="browse_output_folder"):
            picked_output = browse_for_folder(path_from_saved_text(output_folder_text))
            if picked_output is not None:
                pending_output_text = relative_folder_label(picked_output)
                st.session_state["pending_extend_output_text"] = pending_output_text
                st.session_state[output_preset_key] = (
                    pending_output_text
                    if pending_output_text in output_preset_options
                    else "Custom..."
                )
                st.rerun()
        if output_action_cols[1].button("Open", use_container_width=True, key="open_output_folder"):
            open_folder_in_windows(path_from_saved_text(output_folder_text))
        st.caption("This is where API and manual results will be saved.")

    output_dir = resolve_extension_output_dir(output_folder_text)
    if output_dir is None:
        st.error("Output folder is invalid.")
        return

    source_paths = discover_extension_sources(selected_folder)
    if not source_paths:
        st.info("No source images were found for this workflow.")
        return

    folder_key = folder_key_text(selected_folder)
    output_key = folder_key_text(output_dir)
    only_missing = st.checkbox(
        "Show only images without a saved extension",
        value=bool(saved_state.get("only_missing", False)),
        key=f"extend_only_missing::{folder_key}::{output_key}",
    )

    browser_rows = []
    visible_names: list[str] = []
    source_lookup = {path.name: path for path in source_paths}
    for source_path in source_paths:
        variants = extension_target_variants(source_path, output_dir)
        is_ready = bool(variants)
        browser_rows.append(
            {
                "image": source_path.name,
                "status": "Ready" if is_ready else "Needs extension",
                "target": relative_folder_label(variants[-1]) if variants else relative_folder_label(extension_target_path(source_path, output_dir)),
            }
        )
        if not only_missing or not is_ready:
            visible_names.append(source_path.name)

    if not visible_names:
        st.info("Every image in this folder already has a saved extension in the selected output folder.")
        return

    ready_count = len(source_paths) - len(visible_names) if only_missing else sum(
        1 for source_path in source_paths if extension_target_variants(source_path, output_dir)
    )
    pending_count = len(source_paths) - ready_count
    summary_cols = st.columns(4, gap="small")
    summary_cols[0].markdown(
        f"<div class='extend-summary-card'><span>Source</span><strong>{relative_folder_label(selected_folder)}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[1].markdown(
        f"<div class='extend-summary-card'><span>Output</span><strong>{relative_folder_label(output_dir)}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[2].markdown(
        f"<div class='extend-summary-card'><span>Ready</span><strong>{ready_count}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[3].markdown(
        f"<div class='extend-summary-card'><span>Needs work</span><strong>{pending_count}</strong></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Image browser**")
    st.caption(f"{len(visible_names)} visible out of {len(source_paths)} images in this folder.")

    active_key = f"extend_active::{workflow}::{folder_key}::{output_key}"
    saved_active_image = str(saved_state.get("active_image", ""))
    if active_key not in st.session_state or st.session_state[active_key] not in visible_names:
        st.session_state[active_key] = saved_active_image if saved_active_image in visible_names else visible_names[0]

    current_index = visible_names.index(st.session_state[active_key])
    selected_name = render_extension_nav(
        visible_names,
        browser_rows,
        active_key,
        current_index,
        include_picker=True,
    )

    active_name = selected_name
    source_path = source_lookup[active_name]
    source_key = folder_key_text(source_path)
    target_variants = extension_target_variants(source_path, output_dir)
    variant_options = target_variants if target_variants else [extension_target_path(source_path, output_dir)]
    variant_labels = {
        path: ("Base result" if path.name == source_path.name else path.name)
        for path in variant_options
    }
    variant_key = f"extend_target_variant::{workflow}::{source_key}::{output_key}"
    pending_variant_selection = st.session_state.pop("pending_extend_target_variant", None)
    if pending_variant_selection in variant_options:
        st.session_state[variant_key] = pending_variant_selection
    if variant_key not in st.session_state or st.session_state[variant_key] not in variant_options:
        st.session_state[variant_key] = variant_options[-1]
    target_path = st.session_state[variant_key]
    detected_prompt, detected_profile, detected_ratio, detected_width_multiplier = extension_prompt_for_image(
        str(source_path),
        image_cache_key(source_path),
    )
    judge_result = (
        face_preservation_judge(
            str(source_path),
            image_cache_key(source_path),
            str(target_path),
            image_cache_key(target_path),
        )
        if target_path.exists()
        else None
    )
    prompt_key = f"extend_prompt::{workflow}::{source_key}::{output_key}"
    if prompt_key not in st.session_state:
        st.session_state[prompt_key] = detected_prompt
    local_judge_key = (
        f"extend_local_judge::{workflow}::{source_key}::{output_key}::"
        f"{image_cache_key(source_path)}::{image_cache_key(target_path) if target_path.exists() else 'missing'}"
    )
    ai_judge_key = (
        f"extend_ai_judge::{workflow}::{source_key}::{output_key}::"
        f"{image_cache_key(source_path)}::{image_cache_key(target_path) if target_path.exists() else 'missing'}"
    )

    active_summary_cols = st.columns(3, gap="small")
    active_summary_cols[0].markdown(
        f"<div class='extend-summary-card extend-summary-card--active'><span>Active image</span><strong>{active_name}</strong></div>",
        unsafe_allow_html=True,
    )
    active_summary_cols[1].markdown(
        f"<div class='extend-summary-card'><span>Status</span><strong>{'Ready' if target_path.exists() else 'Needs extension'}</strong></div>",
        unsafe_allow_html=True,
    )
    active_summary_cols[2].markdown(
        f"<div class='extend-summary-card'><span>Prompt profile</span><strong>{detected_profile}</strong></div>",
        unsafe_allow_html=True,
    )
    if target_variants:
        st.selectbox(
            "Saved version",
            options=variant_options,
            key=variant_key,
            format_func=lambda path: variant_labels[path],
            help="Pick which saved extension to compare against the original.",
        )
        target_path = st.session_state[variant_key]

    with st.expander("Browse folder contents", expanded=False):
        st.dataframe(browser_rows, use_container_width=True, hide_index=True, height=220)

    swap_compare_key = f"extend_swap_compare::{folder_key}::{output_key}"
    if swap_compare_key not in st.session_state:
        st.session_state[swap_compare_key] = bool(saved_state.get("swap_compare_sides", True))

    compare_controls = st.columns([1.2, 1, 1, 1.1], gap="small")
    compare_mode = compare_controls[0].radio(
        "Compare mode",
        options=["Overlay slider", "Stacked", "Side by side"],
        horizontal=True,
        label_visibility="collapsed",
    )
    large_view = compare_controls[1].checkbox("Large compare view", value=True)
    swap_compare_sides = compare_controls[2].checkbox(
        "Swap compare sides",
        key=swap_compare_key,
    )
    compare_controls[3].caption("Use left/right buttons above to move quickly through the folder.")
    save_extend_tab_state(
        selected_folder,
        output_folder_text,
        only_missing,
        active_name,
        swap_compare_sides,
        bool(st.session_state["extend_local_judge_enabled"]),
    )

    st.markdown("<div id='extend-compare-anchor'></div>", unsafe_allow_html=True)
    if target_path.exists():
        render_extension_compare(source_path, target_path, compare_mode, large_view, swap_compare_sides)
    else:
        st.image(
            load_display_image_bytes(
                str(source_path),
                2200 if large_view else 1500,
                image_cache_key(source_path),
            ),
            caption=f"Original: {source_path.name}",
            use_container_width=True,
        )
        st.info("No saved extension yet for this image.")

    pending_scroll_anchor = st.session_state.pop("pending_extend_scroll_anchor", "")
    if pending_scroll_anchor:
        render_extend_scroll_restore(pending_scroll_anchor)

    render_extension_nav(
        visible_names,
        browser_rows,
        active_key,
        visible_names.index(active_name),
        include_picker=False,
    )

    action_col, meta_col = st.columns([1.15, 0.85], gap="large")
    with action_col:
        st.markdown("**Create or replace**")
        st.caption("Run the API directly, or open Gemini Web if you want to iterate manually before saving.")
        save_mode_key = f"extend_save_mode::{workflow}::{source_key}::{output_key}"
        if save_mode_key not in st.session_state:
            st.session_state[save_mode_key] = "Save as new version" if target_variants else "Save result"
        save_mode_options = ["Save result"] if not target_variants else ["Save as new version", "Replace selected version"]
        save_mode = st.radio(
            "Save mode",
            options=save_mode_options,
            key=save_mode_key,
            horizontal=True,
            label_visibility="collapsed",
        )
        save_target_path = next_extension_target_path(source_path, output_dir) if save_mode == "Save as new version" else target_path
        st.caption(f"Next save path: {relative_folder_label(save_target_path)}")
        action_buttons = st.columns(2, gap="small")
        action_buttons[0].link_button("Open Gemini Web", "https://gemini.google.com/app", use_container_width=True)
        if action_buttons[1].button(
            "Run with Gemini API",
            use_container_width=True,
            type="primary",
        ):
            with st.spinner("Extending image with Gemini API..."):
                run_extend_image_api(source_path, save_target_path, st.session_state[prompt_key])
            load_display_image_bytes.clear()
            load_compare_data_uri.clear()
            st.session_state["pending_extend_target_variant"] = save_target_path
            st.success(f"Saved API result to {relative_folder_label(save_target_path)}.")
            st.rerun()
        st.markdown("**Prompt**")
        prompt_actions = st.columns([1, 1.2], gap="small")
        if prompt_actions[0].button(
            "Use detected prompt",
            key=f"extend_reset_prompt::{workflow}::{source_key}::{output_key}",
            use_container_width=True,
        ):
            st.session_state[prompt_key] = detected_prompt
            st.rerun()
        prompt_actions[1].caption(
            f"Detected: {detected_profile} | aspect {detected_ratio:.2f} | width x{detected_width_multiplier:.2f} to reach 16:9"
        )
        st.text_area(
            "Prompt for Gemini",
            key=prompt_key,
            height=220,
            help="You can keep the existing prompt or edit it before using Gemini Web.",
        )
        uploaded_result = st.file_uploader(
            "Upload the extended image from Gemini",
            type=["jpg", "jpeg", "png"],
            key=f"extend_upload::{workflow}::{source_key}::{output_key}",
        )
        save_disabled = uploaded_result is None
        if st.button("Save uploaded result", use_container_width=True, disabled=save_disabled):
            save_uploaded_extension(uploaded_result, save_target_path)
            load_display_image_bytes.clear()
            load_compare_data_uri.clear()
            st.session_state["pending_extend_target_variant"] = save_target_path
            st.success(f"Saved {save_target_path.name} to {relative_folder_label(save_target_path.parent)}.")
            st.rerun()

    with meta_col:
        st.markdown("**Details**")
        local_judge_ready, local_judge_reason = local_judge_available()
        local_judge_enabled = st.checkbox(
            "Enable local NN judge",
            key="extend_local_judge_enabled",
            help="Uses local face and person models to rank how well the extension preserved people.",
        )
        save_extend_tab_state(
            selected_folder,
            output_folder_text,
            only_missing,
            active_name,
            swap_compare_sides,
            local_judge_enabled,
        )
        if local_judge_enabled:
            judge_status = "ready" if local_judge_ready else "unavailable"
            st.caption(f"Local judge: {judge_status} — {local_judge_reason}")
            if target_path.exists():
                if st.button(
                    "Run local NN judge",
                    key=f"extend_run_local_judge::{workflow}::{source_key}::{output_key}",
                    use_container_width=True,
                    disabled=not local_judge_ready,
                ):
                    with st.spinner("Running local extension judge..."):
                        st.session_state[local_judge_key] = run_local_extension_judge(source_path, target_path)
                    st.rerun()
        if target_path.exists():
            if st.button(
                "Run AI face judge",
                key=f"extend_run_ai_judge::{workflow}::{source_key}::{output_key}",
                use_container_width=True,
            ):
                with st.spinner("Running AI face judge..."):
                    st.session_state[ai_judge_key] = run_ai_face_judge(source_path, target_path)
                st.rerun()
        st.markdown(
            f"""
            <div class="extend-details-card">
              <div><span>Source path</span><strong>{relative_folder_label(source_path)}</strong></div>
              <div><span>Target save path</span><strong>{relative_folder_label(target_path)}</strong></div>
              <div><span>Status</span><strong>{'Ready' if target_path.exists() else 'Needs extension'}</strong></div>
              <div><span>Prompt profile</span><strong>{detected_profile}</strong></div>
              <div><span>Local NN judge</span><strong>{st.session_state.get(local_judge_key, {}).get('label', 'Not run') if local_judge_enabled and target_path.exists() else ('Disabled' if not local_judge_enabled else 'No saved result yet')}</strong></div>
              <div><span>Face judge</span><strong>{judge_result['label'] if judge_result else 'No saved result yet'}</strong></div>
              <div><span>Position</span><strong>{visible_names.index(active_name) + 1} of {len(visible_names)}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        local_judge_result = st.session_state.get(local_judge_key)
        if local_judge_result:
            summary_text = f"{local_judge_result['label']}: {local_judge_result['reason']}"
            if local_judge_result["label"] == "Good":
                st.success(summary_text)
            elif local_judge_result["label"] == "Review":
                st.warning(summary_text)
            else:
                st.error(summary_text)
            with st.expander("Local NN judge details", expanded=False):
                st.caption(
                    f"overall {local_judge_result['overall_score']:.3f} | "
                    f"face count {local_judge_result['face_count_score']:.3f} | "
                    f"face identity {local_judge_result['face_identity_score']:.3f} | "
                    f"person count {local_judge_result['person_count_score']:.3f} | "
                    f"edge risk {local_judge_result['edge_duplication_risk']:.3f}"
                )
        if judge_result:
            st.caption(
                f"Judge score {judge_result['score']:.3f} | face {judge_result['face_score']:.3f} | center {judge_result['center_score']:.3f}. This is a local heuristic, not true face recognition."
            )
        ai_judge_result = st.session_state.get(ai_judge_key)
        if ai_judge_result:
            st.caption(
                f"AI face judge: {ai_judge_result['verdict']} ({ai_judge_result['score']}/100) — {ai_judge_result['reason']}"
            )


def render_build_movie_tab() -> None:
    st.subheader("Build movie")
    st.caption("Choose the finished 16:9 stills, keep them in order, preview the Kling pairs, then generate clips or stitch the finished segments.")
    saved_state = load_build_tab_state()
    pending_source_folder = st.session_state.pop("pending_build_source_folder", None)
    source_folders = discover_image_folders()
    default_folder = ROOT_DIR / "kling_test"
    initial_source_folder = path_from_saved_text(str(saved_state.get("source_folder", relative_folder_label(default_folder))))
    if pending_source_folder is not None and pending_source_folder not in source_folders:
        source_folders.insert(0, pending_source_folder)
    if initial_source_folder not in source_folders:
        source_folders.insert(0, initial_source_folder)
    if default_folder not in source_folders:
        source_folders.insert(0, default_folder)

    source_key = "build_source_folder"
    if source_key not in st.session_state or st.session_state[source_key] not in source_folders:
        st.session_state[source_key] = initial_source_folder
    if pending_source_folder is not None and pending_source_folder in source_folders:
        st.session_state[source_key] = pending_source_folder

    source_cols = st.columns([1.55, 0.5, 0.45], gap="small")
    selected_folder = source_cols[0].selectbox(
        "Build source folder",
        options=source_folders,
        key=source_key,
        format_func=relative_folder_label,
        help="Choose the folder that contains the final 16:9 stills for Kling.",
    )
    if source_cols[1].button("Browse...", use_container_width=True, key="browse_build_source_folder"):
        picked_source = browse_for_folder(selected_folder)
        if picked_source is not None:
            st.session_state["pending_build_source_folder"] = picked_source
            st.rerun()
    if source_cols[2].button("Open", use_container_width=True, key="open_build_source_folder"):
        open_folder_in_windows(selected_folder)

    source_paths = discover_orderable_images(selected_folder)
    if not source_paths:
        st.info("No image files were found in this folder.")
        return

    available_names = [path.name for path in source_paths]
    source_lookup = {path.name: path for path in source_paths}
    ordered_state_key = f"build_ordered_images::{folder_key_text(selected_folder)}"
    custom_order_key = f"build_custom_order::{folder_key_text(selected_folder)}"
    saved_order = saved_state.get("ordered_images", [])
    saved_folder_label = str(saved_state.get("source_folder", ""))
    saved_custom_order = bool(saved_state.get("custom_order", False))
    use_saved_order = (
        saved_folder_label == relative_folder_label(selected_folder)
        and saved_custom_order
        and isinstance(saved_order, list)
    )
    if custom_order_key not in st.session_state:
        st.session_state[custom_order_key] = use_saved_order
        st.session_state[ordered_state_key] = normalize_ordered_images(saved_order if use_saved_order else [], available_names)
    elif ordered_state_key not in st.session_state:
        st.session_state[ordered_state_key] = normalize_ordered_images(saved_order if use_saved_order else [], available_names)
    else:
        st.session_state[ordered_state_key] = normalize_ordered_images(st.session_state[ordered_state_key], available_names)
    ordered_names = st.session_state[ordered_state_key]

    pending_import_key = f"build_pending_import::{folder_key_text(selected_folder)}"
    pending_import = st.session_state.pop(pending_import_key, None)
    if isinstance(pending_import, dict):
        imported_names = [
            str(name)
            for name in pending_import.get("names", [])
            if isinstance(name, str) and name in available_names and name not in ordered_names
        ]
        if imported_names:
            mode = str(pending_import.get("mode", "after_active"))
            if mode == "end" or not ordered_names:
                ordered_names = ordered_names + imported_names
            else:
                anchor = str(pending_import.get("after", ""))
                insert_at = ordered_names.index(anchor) + 1 if anchor in ordered_names else len(ordered_names)
                ordered_names = ordered_names[:insert_at] + imported_names + ordered_names[insert_at:]
            st.session_state[ordered_state_key] = ordered_names
            st.session_state[custom_order_key] = True
            st.session_state[f"build_current_image::{folder_key_text(selected_folder)}"] = imported_names[0]

    current_image_key = f"build_current_image::{folder_key_text(selected_folder)}"
    if current_image_key not in st.session_state or st.session_state[current_image_key] not in ordered_names:
        st.session_state[current_image_key] = ordered_names[0]

    st.markdown("**Sequence board**")
    st.caption("Drag thumbnails to reorder the movie. Click a thumbnail to make it the active still. Default order is numeric-natural, so `2` stays before `11`.")
    storyboard_items = [
        {
            "id": name,
            "name": name,
            "thumb": load_compare_data_uri(str(source_lookup[name]), 320, image_cache_key(source_lookup[name])),
        }
        for name in ordered_names
    ]
    storyboard_value = render_storyboard_component(
        storyboard_items,
        st.session_state[current_image_key],
        component_key=f"build_storyboard::{folder_key_text(selected_folder)}",
    )
    if isinstance(storyboard_value, dict):
        new_order = storyboard_value.get("ordered_ids", [])
        if isinstance(new_order, list):
            normalized_order = normalize_ordered_images(
                [str(name) for name in new_order],
                available_names,
            )
            if normalized_order != ordered_names:
                st.session_state[ordered_state_key] = normalized_order
                ordered_names = normalized_order
                st.session_state[custom_order_key] = True
        selected_name = str(storyboard_value.get("selected_id", "")).strip()
        if selected_name in ordered_names:
            st.session_state[current_image_key] = selected_name

    current_name = st.session_state[current_image_key]
    current_index = ordered_names.index(current_name)
    sequence_cols = st.columns([1.05, 0.95], gap="large")
    with sequence_cols[0]:
        action_cols = st.columns(4, gap="small")
        if action_cols[0].button("Move left", use_container_width=True, disabled=current_index == 0):
            ordered_names[current_index - 1], ordered_names[current_index] = ordered_names[current_index], ordered_names[current_index - 1]
            st.session_state[ordered_state_key] = ordered_names
            st.session_state[custom_order_key] = True
            st.rerun()
        if action_cols[1].button("Move right", use_container_width=True, disabled=current_index == len(ordered_names) - 1):
            ordered_names[current_index + 1], ordered_names[current_index] = ordered_names[current_index], ordered_names[current_index + 1]
            st.session_state[ordered_state_key] = ordered_names
            st.session_state[custom_order_key] = True
            st.rerun()
        if action_cols[2].button("Remove selected", use_container_width=True, disabled=len(ordered_names) <= 2):
            ordered_names.remove(current_name)
            st.session_state[ordered_state_key] = ordered_names
            st.session_state[current_image_key] = ordered_names[max(0, min(current_index, len(ordered_names) - 1))]
            st.session_state[custom_order_key] = True
            st.rerun()
        if action_cols[3].button("Use natural order", use_container_width=True):
            st.session_state[ordered_state_key] = normalize_ordered_images([], available_names)
            st.session_state[current_image_key] = st.session_state[ordered_state_key][0]
            st.session_state[custom_order_key] = False
            st.rerun()
        nav_cols = st.columns(2, gap="small")
        if nav_cols[0].button("Previous still", use_container_width=True, disabled=current_index == 0):
            st.session_state[current_image_key] = ordered_names[current_index - 1]
            st.rerun()
        if nav_cols[1].button("Next still", use_container_width=True, disabled=current_index == len(ordered_names) - 1):
            st.session_state[current_image_key] = ordered_names[current_index + 1]
            st.rerun()

        previous_name = ordered_names[current_index - 1] if current_index > 0 else "Start of sequence"
        next_name = ordered_names[current_index + 1] if current_index < len(ordered_names) - 1 else "End of sequence"
        suggested_pair_label = (
            f"{Path(current_name).stem}_to_{Path(next_name).stem}"
            if current_index < len(ordered_names) - 1
            else f"{Path(previous_name).stem}_to_{Path(current_name).stem}"
        )
        st.markdown(
            f"""
            <div class="extend-details-card">
              <div><span>Active still</span><strong>{current_name}</strong></div>
              <div><span>Position</span><strong>{current_index + 1} of {len(ordered_names)}</strong></div>
              <div><span>Previous</span><strong>{previous_name}</strong></div>
              <div><span>Next</span><strong>{next_name}</strong></div>
              <div><span>Suggested transition</span><strong>{suggested_pair_label}</strong></div>
              <div><span>Sequence mode</span><strong>{'Custom order' if st.session_state[custom_order_key] else 'Natural order'}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with sequence_cols[1]:
        with st.expander("Add back images", expanded=False):
            excluded_names = [name for name in available_names if name not in ordered_names]
            if excluded_names:
                add_name = st.selectbox(
                    "Excluded images",
                    options=excluded_names,
                    key=f"build_add_image::{folder_key_text(selected_folder)}",
                    label_visibility="collapsed",
                )
                if st.button("Add to end", use_container_width=True, key=f"build_add_image_button::{folder_key_text(selected_folder)}"):
                    st.session_state[ordered_state_key] = ordered_names + [add_name]
                    st.session_state[current_image_key] = add_name
                    st.session_state[custom_order_key] = True
                    st.rerun()
            else:
                st.caption("All images in this folder are already in the sequence.")
        st.markdown(
            f"""
            <div class="extend-summary-card">
              <span>Folder</span><strong>{relative_folder_label(selected_folder)}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Add from another folder", expanded=False):
            pending_pool_folder = st.session_state.pop("pending_build_pool_folder", None)
            pool_folders = [folder for folder in discover_image_folders() if folder.resolve() != selected_folder.resolve()]
            initial_pool_folder = path_from_saved_text(str(saved_state.get("pool_folder", relative_folder_label(selected_folder))))
            if initial_pool_folder.resolve() == selected_folder.resolve():
                initial_pool_folder = pool_folders[0] if pool_folders else selected_folder
            if pending_pool_folder is not None and pending_pool_folder not in pool_folders:
                pool_folders.insert(0, pending_pool_folder)
            if initial_pool_folder not in pool_folders and pool_folders:
                pool_folders.insert(0, initial_pool_folder)
            if not pool_folders:
                st.caption("No additional image folders were found.")
            else:
                pool_folder_key = "build_pool_folder"
                if pool_folder_key not in st.session_state or st.session_state[pool_folder_key] not in pool_folders:
                    st.session_state[pool_folder_key] = initial_pool_folder
                if pending_pool_folder is not None and pending_pool_folder in pool_folders:
                    st.session_state[pool_folder_key] = pending_pool_folder

                pool_cols = st.columns([1.4, 0.45, 0.35], gap="small")
                pool_folder = pool_cols[0].selectbox(
                    "Pool folder",
                    options=pool_folders,
                    key=pool_folder_key,
                    format_func=relative_folder_label,
                    help="Pick another folder and add selected stills into this movie sequence.",
                )
                if pool_cols[1].button("Browse...", use_container_width=True, key="browse_build_pool_folder"):
                    picked_pool = browse_for_folder(pool_folder)
                    if picked_pool is not None:
                        st.session_state["pending_build_pool_folder"] = picked_pool
                        st.rerun()
                if pool_cols[2].button("Open", use_container_width=True, key="open_build_pool_folder"):
                    open_folder_in_windows(pool_folder)

                pool_paths = discover_orderable_images(pool_folder)
                pool_ids = [str(path) for path in pool_paths]
                selected_pool_key = f"build_pool_selection::{folder_key_text(selected_folder)}::{folder_key_text(pool_folder)}"
                if selected_pool_key not in st.session_state:
                    st.session_state[selected_pool_key] = []
                current_pool_selection = {
                    item
                    for item in st.session_state[selected_pool_key]
                    if item in pool_ids
                }
                st.session_state[selected_pool_key] = sorted(current_pool_selection)

                st.caption(f"{len(pool_paths)} image(s) available in {relative_folder_label(pool_folder)}.")
                thumb_columns = st.columns(4, gap="small")
                for index, pool_path in enumerate(pool_paths):
                    with thumb_columns[index % 4]:
                        st.image(
                            load_display_image_bytes(str(pool_path), 320, image_cache_key(pool_path)),
                            caption=pool_path.name,
                            use_container_width=True,
                        )
                        checked = str(pool_path) in current_pool_selection
                        if st.checkbox(
                            "Select",
                            value=checked,
                            key=f"build_pool_pick::{folder_key_text(selected_folder)}::{folder_key_text(pool_folder)}::{pool_path.name}",
                        ):
                            current_pool_selection.add(str(pool_path))
                        else:
                            current_pool_selection.discard(str(pool_path))
                st.session_state[selected_pool_key] = sorted(current_pool_selection)

                import_cols = st.columns(2, gap="small")
                if import_cols[0].button(
                    "Add selected after active still",
                    use_container_width=True,
                    key=f"build_import_after::{folder_key_text(selected_folder)}::{folder_key_text(pool_folder)}",
                    disabled=not st.session_state[selected_pool_key],
                ):
                    imported_names: list[str] = []
                    for pool_item in st.session_state[selected_pool_key]:
                        pool_path = Path(pool_item)
                        target_path = next_import_target_path(pool_path, selected_folder)
                        shutil.copy2(pool_path, target_path)
                        imported_names.append(target_path.name)
                    st.session_state[pending_import_key] = {
                        "mode": "after_active",
                        "after": current_name,
                        "names": imported_names,
                    }
                    st.session_state[selected_pool_key] = []
                    st.success(f"Imported {len(imported_names)} image(s) into {relative_folder_label(selected_folder)}.")
                    st.rerun()
                if import_cols[1].button(
                    "Add selected to end",
                    use_container_width=True,
                    key=f"build_import_end::{folder_key_text(selected_folder)}::{folder_key_text(pool_folder)}",
                    disabled=not st.session_state[selected_pool_key],
                ):
                    imported_names = []
                    for pool_item in st.session_state[selected_pool_key]:
                        pool_path = Path(pool_item)
                        target_path = next_import_target_path(pool_path, selected_folder)
                        shutil.copy2(pool_path, target_path)
                        imported_names.append(target_path.name)
                    st.session_state[pending_import_key] = {
                        "mode": "end",
                        "names": imported_names,
                    }
                    st.session_state[selected_pool_key] = []
                    st.success(f"Imported {len(imported_names)} image(s) into {relative_folder_label(selected_folder)}.")
                    st.rerun()

    pair_rows = []
    sequence_pairs = build_pairs_from_sequence(ordered_names)
    for start_name, end_name, pair_key in sequence_pairs:
        pair_rows.append(
            {
                "pair_key": pair_key,
                "start": start_name,
                "end": end_name,
                "prompt": PAIR_PROMPTS.get(pair_key, FALLBACK_PROMPT),
            }
        )
    suggested_preview_key = pair_rows[min(current_index, len(pair_rows) - 1)]["pair_key"] if pair_rows else ""

    selected_pairs_key = f"build_selected_pairs::{folder_key_text(selected_folder)}"
    saved_pair_keys = saved_state.get("selected_pair_keys", [])
    default_pair_keys = [row["pair_key"] for row in pair_rows]
    if selected_pairs_key not in st.session_state:
        if isinstance(saved_pair_keys, list):
            saved_set = set(saved_pair_keys)
            st.session_state[selected_pairs_key] = [row["pair_key"] for row in pair_rows if row["pair_key"] in saved_set] or default_pair_keys
        else:
            st.session_state[selected_pairs_key] = default_pair_keys
    else:
        current_selected = set(st.session_state[selected_pairs_key])
        st.session_state[selected_pairs_key] = [row["pair_key"] for row in pair_rows if row["pair_key"] in current_selected] or default_pair_keys

    save_build_tab_state(
        selected_folder,
        ordered_names,
        st.session_state[selected_pairs_key],
        st.session_state[custom_order_key],
        st.session_state.get("build_pool_folder"),
    )

    summary_cols = st.columns(4, gap="small")
    summary_cols[0].markdown(
        f"<div class='extend-summary-card'><span>Source</span><strong>{relative_folder_label(selected_folder)}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[1].markdown(
        f"<div class='extend-summary-card'><span>Images</span><strong>{len(ordered_names)}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[2].markdown(
        f"<div class='extend-summary-card'><span>Pairs</span><strong>{len(pair_rows)}</strong></div>",
        unsafe_allow_html=True,
    )
    existing_segments = ordered_segment_files_for_sequence(ordered_names, os.path.join(selected_folder, "videos"))
    summary_cols[3].markdown(
        f"<div class='extend-summary-card'><span>Segments ready</span><strong>{len(existing_segments)}</strong></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Pair preview**")
    pair_keys = [row["pair_key"] for row in pair_rows]
    missing_pair_keys = [
        row["pair_key"]
        for row in pair_rows
        if f"seg_{row['pair_key']}.mp4" not in existing_segments
    ]
    selected_count = len(st.session_state[selected_pairs_key])
    missing_count = len(missing_pair_keys)
    pair_summary_cols = st.columns(3, gap="small")
    pair_summary_cols[0].markdown(
        f"<div class='extend-summary-card'><span>Selected pairs</span><strong>{selected_count}</strong></div>",
        unsafe_allow_html=True,
    )
    pair_summary_cols[1].markdown(
        f"<div class='extend-summary-card'><span>Missing segments</span><strong>{missing_count}</strong></div>",
        unsafe_allow_html=True,
    )
    pair_summary_cols[2].markdown(
        f"<div class='extend-summary-card'><span>Preview focus</span><strong>{suggested_preview_key or 'None'}</strong></div>",
        unsafe_allow_html=True,
    )
    pair_action_cols = st.columns(3, gap="small")
    if pair_action_cols[0].button("Select all pairs", use_container_width=True, key=f"build_select_all::{folder_key_text(selected_folder)}"):
        st.session_state[selected_pairs_key] = pair_keys
        save_build_tab_state(selected_folder, ordered_names, st.session_state[selected_pairs_key], st.session_state[custom_order_key])
        st.rerun()
    if pair_action_cols[1].button("Only missing segments", use_container_width=True, key=f"build_select_missing::{folder_key_text(selected_folder)}"):
        st.session_state[selected_pairs_key] = missing_pair_keys or pair_keys
        save_build_tab_state(selected_folder, ordered_names, st.session_state[selected_pairs_key], st.session_state[custom_order_key])
        st.rerun()
    if pair_action_cols[2].button("Clear selection", use_container_width=True, key=f"build_clear_pairs::{folder_key_text(selected_folder)}"):
        st.session_state[selected_pairs_key] = []
        save_build_tab_state(selected_folder, ordered_names, st.session_state[selected_pairs_key], st.session_state[custom_order_key])
        st.rerun()
    with st.expander("Customize pair selection", expanded=False):
        st.multiselect(
            "Pairs to generate",
            options=pair_keys,
            key=selected_pairs_key,
            help="Choose which consecutive pairs to send to Kling from this sequence.",
        )
    save_build_tab_state(
        selected_folder,
        ordered_names,
        st.session_state[selected_pairs_key],
        st.session_state[custom_order_key],
        st.session_state.get("build_pool_folder"),
    )

    preview_key = f"build_preview_pair::{folder_key_text(selected_folder)}"
    preview_options = [row["pair_key"] for row in pair_rows]
    if preview_key not in st.session_state or st.session_state[preview_key] not in preview_options:
        st.session_state[preview_key] = suggested_preview_key or preview_options[0]
    preview_index = preview_options.index(st.session_state[preview_key]) if preview_options else 0
    preview_action_cols = st.columns([1.1, 1.1, 1.3, 1.3, 2.2], gap="small")
    if preview_action_cols[0].button(
        "Previous pair",
        use_container_width=True,
        key=f"build_preview_previous::{folder_key_text(selected_folder)}",
        disabled=preview_index == 0,
    ):
        st.session_state[preview_key] = preview_options[preview_index - 1]
        st.rerun()
    if preview_action_cols[1].button(
        "Next pair",
        use_container_width=True,
        key=f"build_preview_next::{folder_key_text(selected_folder)}",
        disabled=preview_index == len(preview_options) - 1,
    ):
        st.session_state[preview_key] = preview_options[preview_index + 1]
        st.rerun()
    if preview_action_cols[2].button("Preview active transition", use_container_width=True, key=f"build_preview_active::{folder_key_text(selected_folder)}"):
        st.session_state[preview_key] = suggested_preview_key or preview_options[0]
        st.rerun()
    if preview_action_cols[3].button("Preview first missing", use_container_width=True, key=f"build_preview_missing::{folder_key_text(selected_folder)}", disabled=not missing_pair_keys):
        st.session_state[preview_key] = missing_pair_keys[0]
        st.rerun()
    preview_pair_key = st.selectbox("Preview pair", options=preview_options, key=preview_key)
    preview_row = next(row for row in pair_rows if row["pair_key"] == preview_pair_key)
    preview_cols = st.columns(2, gap="large")
    preview_cols[0].image(
        load_display_image_bytes(str(source_lookup[preview_row["start"]]), 1000, image_cache_key(source_lookup[preview_row["start"]])),
        caption=f"Start: {preview_row['start']}",
        use_container_width=True,
    )
    preview_cols[1].image(
        load_display_image_bytes(str(source_lookup[preview_row["end"]]), 1000, image_cache_key(source_lookup[preview_row["end"]])),
        caption=f"End: {preview_row['end']}",
        use_container_width=True,
    )
    st.text_area(
        "Prompt for this pair",
        value=preview_row["prompt"],
        height=140,
        disabled=True,
        key=f"build_prompt_preview::{preview_pair_key}",
    )

    videos_dir = os.path.join(selected_folder, "videos")
    status_path = os.path.join(videos_dir, "status.json")
    action_cols = st.columns([1, 1, 1.2], gap="small")
    use_credits_key = f"build_use_kling::{folder_key_text(selected_folder)}"
    if use_credits_key not in st.session_state:
        st.session_state[use_credits_key] = False
    action_cols[0].checkbox("Use Kling credits", key=use_credits_key)
    if action_cols[1].button("Generate selected pairs", use_container_width=True, type="primary"):
        if not st.session_state[selected_pairs_key]:
            st.warning("Choose at least one pair to generate.")
        elif not st.session_state[use_credits_key]:
            st.warning("Tick `Use Kling credits` before starting Kling generation.")
        else:
            with st.spinner("Generating selected pairs with Kling..."):
                generation_results = generate_pairs_for_sequence(
                    ordered_names,
                    image_dir=str(selected_folder),
                    video_dir=videos_dir,
                    status_path=status_path,
                    selected_keys=st.session_state[selected_pairs_key],
                )
            st.session_state[f"build_generation_results::{folder_key_text(selected_folder)}"] = generation_results
            st.rerun()
    if action_cols[2].button("Stitch available sequence", use_container_width=True):
        try:
            stitch_result = stitch_sequence(
                ordered_names,
                videos_dir=videos_dir,
                output_file=os.path.join(videos_dir, "full_movie.mp4"),
            )
            st.success(f"Stitched {len(stitch_result['segments'])} segments into {relative_folder_label(Path(stitch_result['output_file']))}.")
        except Exception as exc:
            st.error(f"Stitch failed: {exc}")

    generation_results = st.session_state.get(f"build_generation_results::{folder_key_text(selected_folder)}")
    if generation_results:
        st.markdown("**Last generation run**")
        st.dataframe(generation_results, use_container_width=True, hide_index=True, height=260)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(180, 83, 9, 0.18), transparent 24%),
                radial-gradient(circle at top right, rgba(220, 38, 38, 0.10), transparent 22%),
                linear-gradient(180deg, #fbf7f1 0%, #f6efe7 100%);
        }
        [data-testid="stHeader"] {
            display: none;
        }
        [data-testid="stToolbar"] {
            display: none;
        }
        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(31, 41, 55, 0.97) 0%, rgba(55, 65, 81, 0.95) 100%),
                linear-gradient(180deg, #231815 0%, #2f241f 100%);
            border-right: 1px solid rgba(245, 158, 11, 0.18);
        }
        .block-container {
            max-width: 100%;
            padding-top: 0.15rem;
            padding-right: 1.25rem;
            padding-bottom: 1rem;
            padding-left: 1.25rem;
        }
        .hero-banner {
            background:
                linear-gradient(135deg, rgba(20, 24, 33, 0.96) 0%, rgba(39, 25, 18, 0.95) 54%, rgba(114, 47, 34, 0.90) 100%);
            border: 1px solid rgba(245, 158, 11, 0.22);
            border-radius: 18px;
            box-shadow: 0 18px 38px rgba(17, 24, 39, 0.18);
            margin-bottom: 0.45rem;
            padding: 0.9rem 1.35rem 0.8rem;
        }
        .hero-banner h1 {
            color: #fff7ed;
            letter-spacing: -0.03em;
            line-height: 1.02;
            margin: 0 0 0.18rem;
        }
        .hero-banner p {
            color: rgba(255, 237, 213, 0.82);
            font-size: 0.96rem;
            margin: 0;
            max-width: 58rem;
        }
        .extend-summary-card,
        .extend-details-card {
            background: rgba(255, 250, 245, 0.88);
            border: 1px solid rgba(194, 120, 67, 0.18);
            border-radius: 14px;
            box-shadow: 0 10px 22px rgba(78, 45, 24, 0.07);
        }
        .extend-summary-card {
            display: flex;
            flex-direction: column;
            gap: 0.2rem;
            justify-content: space-between;
            min-height: 74px;
            padding: 0.75rem 0.9rem;
        }
        .extend-summary-card--active {
            background: linear-gradient(180deg, rgba(255, 246, 235, 0.98) 0%, rgba(255, 236, 214, 0.92) 100%);
            border-color: rgba(194, 120, 67, 0.28);
        }
        .extend-summary-card span,
        .extend-details-card span {
            color: #8b5e3c;
            display: block;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.01em;
            margin-bottom: 0.22rem;
            text-transform: uppercase;
        }
        .extend-summary-card strong,
        .extend-details-card strong {
            color: #3f2415;
            display: block;
            font-size: 1rem;
            line-height: 1.3;
            overflow-wrap: anywhere;
        }
        .extend-details-card {
            display: grid;
            gap: 0.7rem;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            padding: 0.9rem 1rem;
        }
        .extend-details-card > div {
            background: rgba(255, 255, 255, 0.45);
            border: 1px solid rgba(194, 120, 67, 0.10);
            border-radius: 12px;
            min-height: 78px;
            padding: 0.7rem 0.8rem;
        }
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div {
            color: #f8e7d3;
        }
        [data-testid="stSidebar"] input {
            background: rgba(255, 248, 240, 0.08) !important;
            border: 1px solid rgba(251, 191, 36, 0.16) !important;
            color: #fff7ed !important;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"] p {
            color: #f5e1cc !important;
        }
        [data-testid="stSidebar"] [data-testid="stMetric"],
        [data-testid="stSidebar"] [data-testid="stMetric"] *,
        [data-testid="stSidebar"] [data-testid="stTextInputRootContent"],
        [data-testid="stSidebar"] [data-testid="stTextInputRootContent"] * {
            color: #4b2e1a !important;
        }
        [data-testid="stSidebar"] [data-testid="stMetric"] label {
            color: #7c5a3a !important;
        }
        [data-testid="stSidebar"] [data-testid="stMetricValue"] {
            color: #7c2d12 !important;
            font-weight: 700 !important;
        }
        h1 {
            margin-top: 0;
            margin-bottom: 0.25rem;
        }
        h3 {
            margin-top: 0.35rem;
            margin-bottom: 0.75rem;
        }
        [data-testid="stTabs"] {
            margin-top: 0.05rem;
        }
        [data-baseweb="tab-list"] {
            gap: 0.4rem;
        }
        [data-baseweb="tab"] {
            background: rgba(255, 250, 243, 0.9);
            border: 1px solid #efd9c6;
            border-radius: 999px 999px 0 0;
            padding: 0.35rem 0.9rem;
        }
        [aria-selected="true"][data-baseweb="tab"] {
            background: linear-gradient(180deg, #fff2e2 0%, #fff8f0 100%);
            border-color: #e6b17e;
            color: #9a3412;
        }
        [data-testid="stMetric"] {
            background: rgba(255, 251, 245, 0.92);
            border: 1px solid #edd5bd;
            border-radius: 14px;
            box-shadow: 0 8px 24px rgba(120, 53, 15, 0.06);
            padding: 0.55rem 0.8rem;
        }
        [data-testid="stMetric"] label,
        [data-testid="stMetric"] p {
            margin-bottom: 0;
        }
        [data-testid="stButton"] > button,
        [data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(180deg, #fffaf4 0%, #fff1df 100%);
            border: 1px solid #ddb791;
            border-radius: 14px;
            box-shadow: 0 10px 22px rgba(120, 53, 15, 0.10);
            color: #7c2d12;
            font-weight: 600;
            min-height: 46px;
            padding: 0.65rem 1rem;
            white-space: nowrap;
        }
        [data-testid="stButton"] > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            background: linear-gradient(180deg, #fff5e8 0%, #ffe8cf 100%);
            border-color: #d48a50;
            color: #9a3412;
        }
        button[kind="primary"] {
            background: linear-gradient(180deg, #c85a2b 0%, #8f2d18 100%) !important;
            border-color: #7f1d1d !important;
            color: #fffaf5 !important;
        }
        button[kind="primary"]:hover {
            background: linear-gradient(180deg, #d06a38 0%, #9f3520 100%) !important;
            color: #ffffff !important;
        }
        [data-testid="stButton"] > button:disabled,
        [data-testid="stFormSubmitButton"] > button:disabled,
        button[kind="primary"]:disabled {
            background: linear-gradient(180deg, #f3e7d8 0%, #ead7c2 100%) !important;
            border-color: #d8b896 !important;
            box-shadow: none !important;
            color: #8b5e34 !important;
            opacity: 1 !important;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] > button {
            background: linear-gradient(180deg, #fff3df 0%, #f4d6ad 100%);
            border: 1px solid #d8a468;
            box-shadow: 0 10px 22px rgba(0, 0, 0, 0.18);
            color: #5f2b11;
            font-weight: 700;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] > button *,
        [data-testid="stSidebar"] [data-testid="stFormSubmitButton"] > button * {
            color: inherit !important;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
            background: linear-gradient(180deg, #fff7ea 0%, #f8dfbb 100%);
            border-color: #e3af74;
            color: #7c2d12;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] > button:disabled {
            background: linear-gradient(180deg, rgba(255, 247, 237, 0.18) 0%, rgba(255, 237, 213, 0.14) 100%) !important;
            border-color: rgba(245, 158, 11, 0.18) !important;
            color: rgba(255, 243, 224, 0.72) !important;
        }
        [data-testid="stExpander"] {
            background: rgba(255, 252, 248, 0.9);
            border: 1px solid #efd9c6;
            border-radius: 18px;
            overflow: hidden;
        }
        [data-testid="stExpander"] details summary {
            background: rgba(255, 248, 239, 0.92);
        }
        [data-testid="stForm"] {
            background: rgba(255, 252, 248, 0.88);
            border: 1px solid #efd9c6;
            border-radius: 18px;
            padding: 0.85rem 0.95rem 0.4rem;
        }
        .review-guide {
            border: 1px solid #efd9c6;
            border-radius: 14px;
            padding: 0.75rem 0.9rem;
            background: linear-gradient(180deg, #fff8f0 0%, #fffdf8 100%);
            margin-bottom: 0.8rem;
        }
        .review-summary {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.45rem 0 0.8rem;
        }
        .review-chip {
            background: rgba(255, 251, 245, 0.96);
            border: 1px solid #edd5bd;
            border-radius: 999px;
            color: #7c2d12;
            font-size: 0.88rem;
            font-weight: 600;
            padding: 0.32rem 0.72rem;
            white-space: nowrap;
        }
        .status-pill {
            display: inline-block;
            padding: 0.2rem 0.65rem;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-right: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .status-unreviewed {
            background: #f3f4f6;
            color: #374151;
        }
        .status-approved {
            background: #d7f7df;
            color: #166534;
        }
        .status-redo {
            background: #ffe5bf;
            color: #9a3412;
        }
        .status-discussion {
            background: #e4ebff;
            color: #1d4ed8;
        }
        .compare-focus-shell {
            border: 1px solid rgba(180, 83, 9, 0.18);
            border-radius: 20px;
            box-shadow: 0 22px 48px rgba(17, 24, 39, 0.14);
            padding: 0.85rem 1rem;
            background: linear-gradient(180deg, rgba(255, 250, 245, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
            margin: 0.25rem 0 0.8rem;
        }
        .compare-card-label {
            color: #7c2d12;
            font-size: 0.9rem;
            font-weight: 600;
            margin-bottom: 0.35rem;
        }
        .compare-count {
            align-items: center;
            background: rgba(255, 245, 235, 0.96);
            border: 1px solid #e7c8a9;
            border-radius: 999px;
            color: #9a3412;
            display: inline-flex;
            font-size: 0.82rem;
            font-weight: 700;
            justify-content: center;
            min-height: 46px;
            min-width: 100px;
            padding: 0 0.85rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_controls() -> tuple[str, str]:
    st.sidebar.header("Review Run")
    run_id = st.sidebar.text_input("Run ID", value=DEFAULT_RUN_ID).strip() or DEFAULT_RUN_ID

    st.sidebar.header("Quick view")
    status_filter = st.sidebar.radio(
        "Show",
        options=STATUS_FILTERS,
        index=STATUS_FILTERS.index("Needs review"),
        format_func=lambda item: FILTER_LABELS[item],
        label_visibility="collapsed",
    )

    st.sidebar.caption("Pick a clip, review it, then save or queue a redo.")
    return run_id, status_filter


def select_pair(pairs, pair_rows, status_filter: str):
    filtered_pair_ids = filtered_rows(pair_rows, status_filter)
    pair_ids = [pair.pair_id for pair in pairs]
    visible_pair_ids = [row["pair_id"] for row in filtered_pair_ids]
    pair_row_lookup = {item["pair_id"]: item for item in pair_rows}

    if not visible_pair_ids:
        visible_pair_ids = pair_ids

    pending_pair_id = st.session_state.pop("pending_selected_pair_choice", None)
    if pending_pair_id in visible_pair_ids:
        st.session_state.selected_pair_id = pending_pair_id
        st.session_state.selected_pair_choice = pending_pair_id

    if "selected_pair_id" not in st.session_state:
        st.session_state.selected_pair_id = visible_pair_ids[0]

    if st.session_state.selected_pair_id not in visible_pair_ids:
        st.session_state.selected_pair_id = visible_pair_ids[0]
    if "selected_pair_choice" not in st.session_state:
        st.session_state.selected_pair_choice = st.session_state.selected_pair_id
    if st.session_state.selected_pair_choice not in visible_pair_ids:
        st.session_state.selected_pair_choice = st.session_state.selected_pair_id

    current_index = visible_pair_ids.index(st.session_state.selected_pair_id)
    render_sidebar_queue_summary(pair_rows, visible_pair_ids, current_index)

    button_cols = st.sidebar.columns(2)
    if button_cols[0].button("Previous", use_container_width=True, disabled=current_index == 0):
        set_selected_pair(visible_pair_ids[current_index - 1])
        st.rerun()
    if button_cols[1].button(
        "Next",
        use_container_width=True,
        disabled=current_index == len(visible_pair_ids) - 1,
    ):
        set_selected_pair(visible_pair_ids[current_index + 1])
        st.rerun()

    next_review_pair = next_pair_needing_review(filtered_pair_ids, st.session_state.selected_pair_id)
    if st.sidebar.button(
        "Jump to next unreviewed",
        use_container_width=True,
        disabled=next_review_pair is None,
    ) and next_review_pair is not None:
        set_selected_pair(next_review_pair)
        st.rerun()

    current_row = pair_row_lookup[st.session_state.selected_pair_id]
    st.sidebar.markdown("**Current clip**")
    st.sidebar.caption(
        f"{st.session_state.selected_pair_id} | {display_status(current_row['status'])} | "
        f"{version_summary(current_row)}"
    )
    st.sidebar.caption("[ ] Unreviewed  [R] Needs redo  [OK] Approved  [?] Discussion")

    selected_pair_id = st.sidebar.radio(
        "Queue",
        options=visible_pair_ids,
        key="selected_pair_choice",
        format_func=lambda pair_id: queue_option_label(pair_id, pair_row_lookup[pair_id]),
        label_visibility="collapsed",
    )
    st.session_state.selected_pair_id = selected_pair_id
    return next(pair for pair in pairs if pair.pair_id == selected_pair_id)


def build_pair_rows(pairs, review_lookup, redo_lookup, winners):
    rows = []
    for pair in pairs:
        latest = pair.latest_version()
        if latest is None:
            continue

        status = pair_status(pair.pair_id, latest.version, review_lookup, redo_lookup)
        review = review_lookup.get((pair.pair_id, latest.version))
        winner_version = winners.get(pair.pair_id)
        rows.append(
            {
                "pair_id": pair.pair_id,
                "latest_version": latest.version,
                "winner_version": winner_version,
                "version_count": len(pair.versions),
                "rebuilt": len(pair.versions) > 1,
                "status": status,
                "rating": str(review.rating) if review and review.rating is not None else "-",
            }
        )
    return rows


def render_inbox(pair_rows, status_filter: str, selected_pair_id: str) -> None:
    st.subheader("Inbox")

    visible_rows = filtered_rows(pair_rows, status_filter)
    if not visible_rows:
        st.info("No clips match this filter.")
        visible_rows = pair_rows

    approved = count_rows(pair_rows, "Approved")
    redo = count_rows(pair_rows, "Redo queued")
    discussion = count_rows(pair_rows, "Needs discussion")
    unreviewed = count_rows(pair_rows, "Needs review")

    metric_cols = st.columns(4)
    metric_cols[0].metric("Unreviewed", unreviewed)
    metric_cols[1].metric("Approved", approved)
    metric_cols[2].metric("Needs redo", redo)
    metric_cols[3].metric("Needs discussion", discussion)

    rows = []
    for item in visible_rows:
        rows.append(
            {
                "selected": "*" if item["pair_id"] == selected_pair_id else "",
                "pair": item["pair_id"],
                "latest": f"v{item['latest_version']}",
                "winner": f"v{item['winner_version']}" if item["winner_version"] else "-",
                "versions": item["version_count"],
                "rebuilt": "Yes" if item["rebuilt"] else "-",
                "status": display_status(item["status"]),
                "rating": item["rating"],
            }
        )

    st.caption(f"Showing {len(visible_rows)} of {len(pair_rows)} clips.")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_review_panel(
    selected_pair,
    review_lookup,
    redo_lookup,
    waiting_review_lookup,
    winners,
    run_id: str,
    pair_rows,
    progress,
    status_filter: str,
) -> None:
    st.subheader(pair_label(selected_pair.pair_id))

    version_numbers = [item.version for item in selected_pair.versions]
    version_labels = {item.version: f"v{item.version} - {item.filename}" for item in selected_pair.versions}
    default_version = selected_pair.latest_version().version
    compare_focus_pair_id = st.session_state.get("compare_focus_pair_id")
    if compare_focus_pair_id == selected_pair.pair_id:
        render_compare_focus_mode(selected_pair, version_labels)
        return
    if "selected_version_by_pair" not in st.session_state:
        st.session_state.selected_version_by_pair = {}

    selected_version = st.session_state.selected_version_by_pair.get(selected_pair.pair_id, default_version)
    if selected_version not in version_numbers:
        selected_version = default_version

    main_cols = st.columns([1.55, 0.9], gap="large")

    with main_cols[1]:
        selected_version = st.selectbox(
            "Version",
            options=version_numbers,
            index=version_numbers.index(selected_version),
            format_func=lambda version: version_labels[version],
        )
        st.session_state.selected_version_by_pair[selected_pair.pair_id] = selected_version

    version_map = {item.version: item for item in selected_pair.versions}
    current_clip = version_map[selected_version]
    winner_version = winners.get(selected_pair.pair_id)
    review = review_lookup.get((selected_pair.pair_id, current_clip.version))
    queued_redo = redo_lookup.get((selected_pair.pair_id, current_clip.version))
    waiting_review = waiting_review_lookup.get((selected_pair.pair_id, current_clip.version))
    current_status = pair_status(selected_pair.pair_id, current_clip.version, review_lookup, redo_lookup)

    with main_cols[0]:
        st.video(str(Path(current_clip.video_path)))
        image_cols = st.columns(2, gap="medium")
        start_path = frame_image_path(selected_pair.start_frame_id)
        end_path = frame_image_path(selected_pair.end_frame_id)
        image_cols[0].image(
            str(start_path),
            caption=f"Start: {selected_pair.start_frame_id}",
            use_container_width=True,
        )
        image_cols[1].image(
            str(end_path),
            caption=f"End: {selected_pair.end_frame_id}",
            use_container_width=True,
        )

    with main_cols[1]:
        render_status_banner(current_status, winner_version, current_clip.version)

        st.markdown(
            (
                '<div class="review-summary">'
                f'<span class="review-chip">Reviewed {progress["reviewed"]}/{progress["total"]}</span>'
                f'<span class="review-chip">Unreviewed {progress["unreviewed"]}</span>'
                f'<span class="review-chip">Needs redo {progress["redo"]}</span>'
                f'<span class="review-chip">Selected v{current_clip.version}</span>'
                f'<span class="review-chip">Winner {f"v{winner_version}" if winner_version else "not set"}</span>'
                f'<span class="review-chip">Frames {selected_pair.start_frame_id} -> {selected_pair.end_frame_id}</span>'
                "</div>"
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="review-guide">
            Decide if this version is good enough, needs another try, or should be discussed.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if len(selected_pair.versions) == 1:
            st.caption("Only one version exists for this pair right now.")
        else:
            st.caption("Multiple versions available. Compare them if you need to choose a winner.")
            with st.expander("Compare versions side by side", expanded=waiting_review is not None):
                compare_versions(selected_pair, selected_version, version_labels)

        winner_button_label = "Mark selected version as winner"
        if waiting_review is not None:
            winner_button_label = f"Accept v{current_clip.version} and clear new-version-ready state"
        elif len(selected_pair.versions) > 1:
            winner_button_label = f"Accept v{current_clip.version} as the winner"

        if st.button(winner_button_label, use_container_width=True):
            save_winner(selected_pair.pair_id, current_clip.version, run_id=run_id)
            if waiting_review is not None:
                accept_review_version(selected_pair.pair_id, current_clip.version, run_id=run_id)
                st.success(
                    f"Accepted v{current_clip.version} as the winner for {selected_pair.pair_id} and cleared the waiting-review entry."
                )
            else:
                st.success(f"Saved v{current_clip.version} as the winner for {selected_pair.pair_id}.")
            st.rerun()

        if review is not None:
            st.info(
                f"Last review: {DECISION_LABELS.get(review.decision, review.decision)}"
                f" | Rating: {review.rating if review.rating is not None else '-'}"
                f" | Reviewed at: {review.reviewed_at}"
            )
        if queued_redo is not None:
            st.warning("This version is currently in the redo queue.")
        if waiting_review is not None:
            st.info("This retried version is back. Approve it here or accept it as the winner above.")

        decision = st.radio(
            "Decision",
            options=DECISIONS,
            index=DECISIONS.index(review.decision) if review else 0,
            format_func=lambda item: DECISION_LABELS[item],
            horizontal=True,
            key=f"decision-{selected_pair.pair_id}-{current_clip.version}",
        )

        with st.form(key=f"review-form-{selected_pair.pair_id}-{current_clip.version}"):

            rating_options = ["-"] + [str(number) for number in range(1, 6)]
            saved_rating = str(review.rating) if review and review.rating is not None else "5"
            rating_value = st.select_slider("Quality rating", options=rating_options, value=saved_rating)

            issue_defaults = review.issues if review else []
            note_default = review.note if review else ""
            issues: list[str] = issue_defaults
            note = note_default
            if decision != "approve":
                st.caption("What needs fixing?")
                issues = render_issue_group_inputs(selected_pair.pair_id, current_clip.version, issue_defaults)

                note = st.text_area(
                    "Optional note",
                    value=note_default,
                    placeholder="Example: face morphs in the middle, transition is too dramatic.",
                    height=90,
                )
            else:
                st.caption("Approved clips do not need issue tags or notes.")
                issues = []
                note = ""

            with st.expander("Advanced review options", expanded=False):
                reviewed_by = st.text_input("Reviewer", value=review.reviewed_by if review else "local-user")
                st.write(f"File: `{current_clip.filename}`")
                st.write(f"Path: `{current_clip.video_path}`")

            submit_cols = st.columns(2, gap="medium")
            save_only = submit_cols[0].form_submit_button("Save only", use_container_width=True)
            approve_and_next = submit_cols[1].form_submit_button(
                "Approve and next",
                type="primary",
                use_container_width=True,
                disabled=decision != "approve",
            )
            submitted = save_only or approve_and_next

            if submitted:
                record = ReviewRecord(
                    pair_id=selected_pair.pair_id,
                    version=current_clip.version,
                    decision=decision,
                    rating=None if rating_value == "-" else int(rating_value),
                    issues=issues,
                    note=note.strip(),
                    reviewed_by=reviewed_by.strip() or "local-user",
                )
                save_review(record, run_id=run_id)
                remove_redo_waiting_review(selected_pair.pair_id, current_clip.version, run_id=run_id)

                if decision == "redo":
                    queue_redo(
                        RedoRequest(
                            pair_id=selected_pair.pair_id,
                            source_version=current_clip.version,
                            issues=issues,
                            note=note.strip(),
                        ),
                        run_id=run_id,
                    )
                else:
                    remove_redo_request(selected_pair.pair_id, current_clip.version, run_id=run_id)

                if decision == "approve" and approve_and_next:
                    remaining_unreviewed = remaining_unreviewed_after_save(pair_rows, selected_pair.pair_id)
                    next_pair_id = next_pair_to_review(pair_rows, selected_pair.pair_id)
                    if next_pair_id is not None:
                        set_selected_pair(next_pair_id)
                        st.session_state.review_notice = (
                            f"Approved {selected_pair.pair_id}. {remaining_unreviewed} clips still unreviewed. Moved to {next_pair_id}."
                        )
                    else:
                        st.session_state.review_notice = (
                            f"Approved {selected_pair.pair_id}. {remaining_unreviewed} clips still unreviewed."
                        )
                elif decision == "approve":
                    target_pair_id = next_pair_for_filter(pair_rows, selected_pair.pair_id, "Approved", status_filter)
                    set_selected_pair(target_pair_id)
                    if target_pair_id == selected_pair.pair_id:
                        st.session_state.review_notice = f"Approved {selected_pair.pair_id}. Stayed on this clip."
                    else:
                        st.session_state.review_notice = (
                            f"Approved {selected_pair.pair_id}. It no longer matches this filter, so the queue moved to {target_pair_id}."
                        )
                elif decision == "redo":
                    target_pair_id = next_pair_for_filter(pair_rows, selected_pair.pair_id, "Redo queued", status_filter)
                    set_selected_pair(target_pair_id)
                    st.session_state.review_notice = (
                        f"Queued redo for {selected_pair.pair_id}. {progress['redo'] + 1} clips now need another pass."
                    )
                elif decision == "needs_discussion":
                    target_pair_id = next_pair_for_filter(pair_rows, selected_pair.pair_id, "Needs discussion", status_filter)
                    set_selected_pair(target_pair_id)
                    st.session_state.review_notice = f"Saved discussion note for {selected_pair.pair_id}."
                else:
                    set_selected_pair(selected_pair.pair_id)
                    st.session_state.review_notice = "Review saved."
                st.rerun()


def render_status_banner(status: str, winner_version: int | None, selected_version: int) -> None:
    classes = {
        "Needs review": "status-pill status-unreviewed",
        "Approved": "status-pill status-approved",
        "Redo queued": "status-pill status-redo",
        "Needs discussion": "status-pill status-discussion",
    }
    badge = f'<span class="{classes[status]}">{display_status(status)}</span>'
    winner_text = "This version is not marked as the winner yet."
    if winner_version == selected_version:
        winner_text = "This version is currently marked as the winner."
    elif winner_version is not None:
        winner_text = f"Winner is v{winner_version}."
    st.markdown(f"{badge} {winner_text}", unsafe_allow_html=True)

def render_compare_focus_mode(selected_pair, version_labels) -> None:
    st.markdown('<div class="compare-focus-shell">', unsafe_allow_html=True)
    header_cols = st.columns([1, 1], gap="medium")
    header_cols[0].markdown("**Focused compare mode**")
    if header_cols[1].button("Back to review details", use_container_width=True):
        st.session_state.compare_focus_pair_id = None
        st.rerun()
    st.caption("Review controls are hidden here so the compare videos can use more of the page.")
    compare_versions(selected_pair, selected_pair.latest_version().version, version_labels, focused=True)
    st.markdown("</div>", unsafe_allow_html=True)


def compare_versions(selected_pair, selected_version: int, version_labels, focused: bool = False) -> None:
    version_numbers = [item.version for item in selected_pair.versions]
    version_map = {item.version: item for item in selected_pair.versions}
    selected_versions = compare_version_selection(selected_pair.pair_id, version_numbers, selected_version)

    selected_versions = st.multiselect(
        "Compare versions",
        options=version_numbers,
        default=selected_versions,
        format_func=lambda version: version_labels[version],
        max_selections=4,
        key=f"compare-versions-{selected_pair.pair_id}",
        help="Choose up to four versions to compare side by side.",
    )
    selected_versions = normalized_compare_selection(selected_versions, version_numbers, selected_version)
    st.session_state.compare_versions_by_pair[selected_pair.pair_id] = selected_versions

    action_cols = st.columns([1.1, 0.42], gap="small")
    if focused:
        if action_cols[0].button("Exit compare view", use_container_width=True):
            st.session_state.compare_focus_pair_id = None
            st.rerun()
    else:
        if action_cols[0].button("Open compare view", use_container_width=True):
            st.session_state.compare_focus_pair_id = selected_pair.pair_id
            st.rerun()

    action_cols[1].markdown(
        f"<div class='compare-count'>{len(selected_versions)} selected</div>",
        unsafe_allow_html=True,
    )
    marker_id = compare_marker_id(selected_pair.pair_id, focused)
    render_compare_sync_controls(marker_id, focused)
    render_compare_videos(marker_id, [version_map[version] for version in selected_versions])


def compare_version_selection(pair_id: str, version_numbers: list[int], selected_version: int) -> list[int]:
    if "compare_versions_by_pair" not in st.session_state:
        st.session_state.compare_versions_by_pair = {}
    saved_versions = st.session_state.compare_versions_by_pair.get(pair_id)
    if saved_versions:
        return normalized_compare_selection(saved_versions, version_numbers, selected_version)
    return default_compare_versions(version_numbers, selected_version)


def default_compare_versions(version_numbers: list[int], selected_version: int) -> list[int]:
    if len(version_numbers) == 1:
        return [version_numbers[0]]
    if selected_version not in version_numbers:
        return version_numbers[-2:]
    selected_index = version_numbers.index(selected_version)
    if selected_index == 0:
        return version_numbers[:2]
    return [version_numbers[selected_index - 1], selected_version]


def normalized_compare_selection(selected_versions: list[int], version_numbers: list[int], selected_version: int) -> list[int]:
    valid_versions = [version for version in version_numbers if version in selected_versions]
    if not valid_versions:
        return default_compare_versions(version_numbers, selected_version)
    return valid_versions[:4]


def compare_marker_id(pair_id: str, focused: bool) -> str:
    suffix = "focus" if focused else "inline"
    return f"compare-{pair_id.replace('_', '-')}-{suffix}"


def render_compare_sync_controls(marker_id: str, focused: bool) -> None:
    height = 78 if focused else 72
    mode_label = "focused compare" if focused else "compare"
    script = f"""
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 0.5rem 0;">
      <button onclick="controlCompare('play')" style="padding:0.4rem 0.8rem;border-radius:999px;border:1px solid #d9dde7;background:#ffffff;cursor:pointer;">Play all</button>
      <button onclick="controlCompare('pause')" style="padding:0.4rem 0.8rem;border-radius:999px;border:1px solid #d9dde7;background:#ffffff;cursor:pointer;">Pause all</button>
      <button onclick="controlCompare('restart')" style="padding:0.4rem 0.8rem;border-radius:999px;border:1px solid #d9dde7;background:#ffffff;cursor:pointer;">Restart all</button>
      <button onclick="controlCompare('fullscreen')" style="padding:0.4rem 0.8rem;border-radius:999px;border:1px solid #d9dde7;background:#ffffff;cursor:pointer;">Fullscreen compare</button>
      <span id="compare-status" style="font-size:0.82rem;color:#475569;">Use the buttons above or each player's native controls.</span>
    </div>
    <script>
    const markerId = {json.dumps(marker_id)};
    const modeLabel = {json.dumps(mode_label)};
    function getCompareNodes() {{
      try {{
        const doc = window.parent.document;
        const frame = window.frameElement;
        const frameContainer = frame?.parentElement?.parentElement;
        if (frameContainer) {{
          const scopedVideos = Array.from(frameContainer.querySelectorAll('video'));
          if (scopedVideos.length) {{
            return {{
              start: null,
              end: null,
              videos: scopedVideos,
              container: frameContainer
            }};
          }}
        }}
        const start = doc.getElementById(`${{markerId}}-start`);
        const end = doc.getElementById(`${{markerId}}-end`);
        if (!start || !end) {{
          return {{start: null, end: null, videos: [], container: null}};
        }}
        const videos = [];
        let node = start.nextElementSibling;
        while (node && node !== end) {{
          videos.push(...node.querySelectorAll('video'));
          node = node.nextElementSibling;
        }}
        return {{
          start,
          end,
          videos,
          container: start.closest('[data-testid="stVerticalBlock"]')
        }};
      }} catch (error) {{
        return {{start: null, end: null, videos: [], container: null, error}};
      }}
    }}
    function setStatus(message) {{
      const label = document.getElementById('compare-status');
      if (label) {{
        label.textContent = message;
      }}
    }}
    async function controlCompare(action) {{
      const {{videos, container, error}} = getCompareNodes();
      if (error) {{
        setStatus(`Shared controls are unavailable in this browser. Use each player's controls instead.`);
        return;
      }}
      if (!videos.length) {{
        setStatus(`No videos found in this ${{modeLabel}} view yet.`);
        return;
      }}
      if (action === 'pause') {{
        videos.forEach((video) => video.pause());
        setStatus(`Paused ${{videos.length}} video(s).`);
        return;
      }}
      if (action === 'restart') {{
        videos.forEach((video) => {{
          video.pause();
          video.currentTime = 0;
        }});
        const results = await Promise.allSettled(videos.map((video) => video.play()));
        const failed = results.filter((result) => result.status === 'rejected').length;
        setStatus(failed ? `Restarted ${{videos.length - failed}} video(s). Some browsers blocked autoplay.` : `Restarted ${{videos.length}} video(s) from the beginning.`);
        return;
      }}
      if (action === 'play') {{
        videos.forEach((video) => {{
          if (video.currentTime < 0.05) {{
            video.currentTime = 0;
          }}
        }});
        const results = await Promise.allSettled(videos.map((video) => video.play()));
        const failed = results.filter((result) => result.status === 'rejected').length;
        setStatus(failed ? `Played ${{videos.length - failed}} video(s). Some browsers blocked autoplay.` : `Playing ${{videos.length}} video(s) together.`);
        return;
      }}
      if (action === 'fullscreen') {{
        if (container && container.requestFullscreen) {{
          await container.requestFullscreen();
          setStatus(`Opened the ${{modeLabel}} in fullscreen.`);
        }} else {{
          setStatus(`Fullscreen is unavailable here. Use each player's native fullscreen button.`);
        }}
      }}
    }}
    </script>
    """
    components.html(script, height=height)


def render_compare_videos(marker_id: str, selected_versions) -> None:
    st.markdown(f"<div id='{marker_id}-start'></div>", unsafe_allow_html=True)
    total_versions = len(selected_versions)

    if total_versions == 1:
        render_compare_card(selected_versions[0], full_width=True)
    elif total_versions == 2:
        compare_cols = st.columns(2, gap="large")
        for column, clip in zip(compare_cols, selected_versions, strict=False):
            with column:
                render_compare_card(clip)
    else:
        for row_start in range(0, total_versions, 2):
            row_clips = selected_versions[row_start : row_start + 2]
            compare_cols = st.columns(2, gap="large")
            for index, clip in enumerate(row_clips):
                with compare_cols[index]:
                    render_compare_card(clip)
    st.markdown(f"<div id='{marker_id}-end'></div>", unsafe_allow_html=True)


def render_compare_card(clip, full_width: bool = False) -> None:
    st.markdown(
        f"<div class='compare-card-label'>v{clip.version} - {clip.filename}</div>",
        unsafe_allow_html=True,
    )
    st.video(str(Path(clip.video_path)))
    if full_width:
        st.caption("Use the player's native fullscreen button for the largest single-video view.")


def render_redo_queue(redo_requests, review_lookup, winners, run_id: str) -> None:
    st.subheader("Redo queue")
    if not redo_requests:
        st.info("No clips are queued for redo.")
        return

    queued_requests = [item for item in redo_requests if item.status == "queued"]
    waiting_review_requests = [item for item in redo_requests if item.status == "waiting_review"]
    failed_requests = [item for item in redo_requests if item.status == "failed"]

    metric_cols = st.columns(3)
    metric_cols[0].metric("Queued to rerun", len(queued_requests))
    metric_cols[1].metric("New version ready", len(waiting_review_requests))
    metric_cols[2].metric("Retry failed", len(failed_requests))

    st.caption("Queued items can be sent to Kling. New version ready items already produced a retry and are waiting for review.")

    selected_queue_keys = []
    queued_request_by_key = {}
    if queued_requests:
        options = [redo_request_key(item.pair_id, item.source_version) for item in queued_requests]
        labels = {
            redo_request_key(item.pair_id, item.source_version): (
                f"{item.pair_id} from v{item.source_version}"
            )
            for item in queued_requests
        }
        queued_request_by_key = {
            redo_request_key(item.pair_id, item.source_version): item for item in queued_requests
        }
        selected_queue_keys = st.multiselect(
            "Queued items to run",
            options=options,
            default=options,
            format_func=lambda key: labels[key],
            help="Choose exactly which queued retries to preview or run.",
        )

    control_cols = st.columns([1, 1, 1.2], gap="large")
    if control_cols[0].button("Preview queued retries", use_container_width=True):
        if not selected_queue_keys:
            st.warning("Select at least one queued retry to preview.")
        else:
            st.session_state.redo_preview = preview_redo_queue(run_id, set(selected_queue_keys))

    run_confirmed = control_cols[1].checkbox("Use Kling credits", value=False)
    if control_cols[2].button(
        "Run queued retries",
        use_container_width=True,
        disabled=not queued_requests or not selected_queue_keys,
        type="primary",
    ):
        if not run_confirmed:
            st.warning("Tick 'Use Kling credits' before running queued retries.")
        elif not selected_queue_keys:
            st.warning("Select at least one queued retry to run.")
        else:
            try:
                with st.spinner("Submitting queued retries to Kling..."):
                    st.session_state.redo_results = run_redo_queue(run_id, set(selected_queue_keys))
                    st.session_state.redo_preview = []
            except Exception as error:
                st.session_state.redo_run_error = f"Retry run failed: {error}"
            st.rerun()

    preview_rows = st.session_state.get("redo_preview", [])
    if preview_rows:
        st.markdown("**Queued retry preview**")
        st.dataframe(
            [
                {
                    "pair": item["pair_id"],
                    "from": f"v{item['source_version']}",
                    "to": f"v{item['target_version']}",
                    "output_file": item["output_file"],
                    "prompt_mode": item["prompt_mode"],
                    "issues": item["issues"],
                }
                for item in preview_rows
            ],
            use_container_width=True,
            hide_index=True,
        )
        for item in preview_rows:
            with st.expander(f"{item['pair_id']} retry prompt", expanded=False):
                queue_key = redo_request_key(item["pair_id"], item["source_version"])
                queued_item = queued_request_by_key.get(queue_key)
                active_override = queued_item.prompt_override if queued_item else ""
                draft_key = f"editable-override-{item['pair_id']}-{item['source_version']}"
                pending_key = f"pending-override-{item['pair_id']}-{item['source_version']}"
                draft_source_key = f"draft-source-{item['pair_id']}-{item['source_version']}"

                pending_prompt = st.session_state.pop(pending_key, None)
                if pending_prompt is not None:
                    st.session_state[draft_key] = pending_prompt
                if draft_key not in st.session_state:
                    st.session_state[draft_key] = active_override or item["retry_prompt"]
                if draft_source_key not in st.session_state:
                    st.session_state[draft_source_key] = item["prompt_mode"]

                source_mode = "manual_override" if active_override else st.session_state[draft_source_key]
                source_label = {
                    "llm_rewrite": "Gemini automatic rewrite",
                    "rule_based": "Rule-based fallback",
                    "manual_override": "Manual override",
                }.get(source_mode, source_mode)
                st.caption(f"Current prompt source: {source_label}")

                prompt_cols = st.columns(3, gap="medium")
                if prompt_cols[0].button(
                    "Generate new prompt",
                    key=f"generate-prompt-{item['pair_id']}-{item['source_version']}",
                    use_container_width=True,
                ):
                    new_prompt, new_mode = generate_automatic_retry_prompt(
                        item["pair_id"],
                        queued_item.issues if queued_item else [],
                        queued_item.note if queued_item else "",
                    )
                    st.session_state[pending_key] = new_prompt
                    st.session_state[draft_source_key] = new_mode
                    st.rerun()

                use_edited = prompt_cols[1].button(
                    "Use edited prompt for retry",
                    key=f"use-edited-override-{item['pair_id']}-{item['source_version']}",
                    use_container_width=True,
                )
                reset_prompt = prompt_cols[2].button(
                    "Return to automatic prompt",
                    key=f"clear-edited-override-{item['pair_id']}-{item['source_version']}",
                    use_container_width=True,
                    disabled=not active_override,
                )

                st.caption(
                    "Edit this prompt if you want. The retry stays automatic until you press 'Use edited prompt for retry'."
                )
                st.text_area(
                    "Editable retry prompt",
                    key=draft_key,
                    height=160,
                )

                if active_override:
                    st.info("Manual override is active for this retry.")
                else:
                    st.caption("Automatic rewrite is active for this retry.")

                if use_edited:
                    edited_prompt = st.session_state[draft_key].strip()
                    if edited_prompt:
                        set_redo_prompt_override(
                            item["pair_id"],
                            item["source_version"],
                            st.session_state[draft_key],
                            run_id=run_id,
                        )
                        st.session_state.redo_preview = preview_redo_queue(run_id, set(selected_queue_keys))
                        st.session_state.redo_results = []
                        st.session_state.redo_run_error = ""
                        st.session_state.review_notice = (
                            f"Edited prompt is now active for {item['pair_id']}."
                        )
                        st.rerun()
                    else:
                        st.warning("Generate or edit a prompt first.")

                if reset_prompt:
                    set_redo_prompt_override(item["pair_id"], item["source_version"], "", run_id=run_id)
                    auto_prompt, auto_mode = generate_automatic_retry_prompt(
                        item["pair_id"],
                        queued_item.issues if queued_item else [],
                        queued_item.note if queued_item else "",
                    )
                    st.session_state[pending_key] = auto_prompt
                    st.session_state[draft_source_key] = auto_mode
                    st.session_state.redo_preview = preview_redo_queue(run_id, set(selected_queue_keys))
                    st.session_state.redo_results = []
                    st.session_state.redo_run_error = ""
                    st.session_state.review_notice = (
                        f"Automatic prompt restored for {item['pair_id']}."
                    )
                    st.rerun()

    result_rows = st.session_state.get("redo_results", [])
    if result_rows:
        st.markdown("**Last retry run**")
        st.dataframe(result_rows, use_container_width=True, hide_index=True)

    st.markdown("**Queued to rerun**")
    render_redo_request_table(queued_requests, review_lookup, winners)

    if waiting_review_requests:
        st.markdown("**New version ready**")
        render_redo_request_table(waiting_review_requests, review_lookup, winners)

    if failed_requests:
        st.markdown("**Retry failed**")
        render_redo_request_table(failed_requests, review_lookup, winners)


def render_redo_request_table(redo_requests, review_lookup, winners) -> None:
    rows: list[dict[str, str | int]] = []
    for item in redo_requests:
        review = review_lookup.get((item.pair_id, item.source_version))
        rows.append(
            {
                "pair": item.pair_id,
                "source_version": f"v{item.source_version}",
                "target_version": f"v{item.target_version}" if item.target_version else "-",
                "status": display_status(item.status),
                "issues": ", ".join(ISSUE_LABELS[tag] for tag in item.issues) if item.issues else "-",
                "note": item.note or "-",
                "prompt_source": "Manual override" if item.prompt_override else "Auto rewrite",
                "winner": f"v{winners[item.pair_id]}" if item.pair_id in winners else "-",
                "decision": DECISION_LABELS.get(review.decision, "-") if review else "-",
                "output_file": item.output_file or "-",
                "error": item.error or "-",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def filtered_rows(pair_rows, status_filter: str):
    if status_filter == "All clips":
        return pair_rows
    if status_filter == "Rebuilt clips":
        return [item for item in pair_rows if item["rebuilt"]]
    if status_filter == "Needs review":
        return [item for item in pair_rows if item["status"] == "Needs review"]
    if status_filter == "Redo queue":
        return [item for item in pair_rows if item["status"] == "Redo queued"]
    if status_filter == "Approved":
        return [item for item in pair_rows if item["status"] == "Approved"]
    return [item for item in pair_rows if item["status"] == "Needs discussion"]


def pair_status(pair_id: str, version: int, review_lookup, redo_lookup) -> str:
    if (pair_id, version) in redo_lookup:
        return "Redo queued"

    review = review_lookup.get((pair_id, version))
    if review is None:
        return "Needs review"
    if review.decision == "approve":
        return "Approved"
    if review.decision == "redo":
        return "Redo queued"
    return "Needs discussion"


def count_rows(pair_rows, status: str) -> int:
    return sum(1 for item in pair_rows if item["status"] == status)


def progress_counts(pair_rows) -> dict[str, int]:
    total = len(pair_rows)
    unreviewed = count_rows(pair_rows, "Needs review")
    approved = count_rows(pair_rows, "Approved")
    redo = count_rows(pair_rows, "Redo queued")
    discussion = count_rows(pair_rows, "Needs discussion")
    reviewed = total - unreviewed
    return {
        "total": total,
        "reviewed": reviewed,
        "unreviewed": unreviewed,
        "approved": approved,
        "redo": redo,
        "discussion": discussion,
    }


def next_pair_for_filter(pair_rows, current_pair_id: str, new_status: str, status_filter: str) -> str:
    updated_rows = []
    for item in pair_rows:
        if item["pair_id"] == current_pair_id:
            updated = dict(item)
            updated["status"] = new_status
            updated_rows.append(updated)
        else:
            updated_rows.append(item)

    visible_rows = filtered_rows(updated_rows, status_filter)
    visible_pair_ids = [item["pair_id"] for item in visible_rows]
    if not visible_pair_ids:
        return current_pair_id
    if current_pair_id in visible_pair_ids:
        return current_pair_id

    pair_ids = [item["pair_id"] for item in updated_rows]
    current_index = pair_ids.index(current_pair_id) if current_pair_id in pair_ids else -1
    ordered_rows = updated_rows[current_index + 1 :] + updated_rows[:current_index]
    for item in ordered_rows:
        if item["pair_id"] in visible_pair_ids:
            return item["pair_id"]
    return visible_pair_ids[0]


def remaining_unreviewed_after_save(pair_rows, current_pair_id: str) -> int:
    remaining = count_rows(pair_rows, "Needs review")
    current_row = next((item for item in pair_rows if item["pair_id"] == current_pair_id), None)
    if current_row is not None and current_row["status"] == "Needs review":
        return max(0, remaining - 1)
    return remaining


def display_status(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def queue_option_label(pair_id: str, row: dict[str, str | int | bool | None]) -> str:
    return f"{status_short(str(row['status']))} {pair_id} {version_summary(row)}"


def render_issue_group_inputs(pair_id: str, version: int, issue_defaults: list[str]) -> list[str]:
    selected: list[str] = []
    for group_name, group_issues in ISSUE_GROUPS:
        defaults = [item for item in issue_defaults if item in group_issues]
        group_selected = st.multiselect(
            group_name,
            options=group_issues,
            default=defaults,
            format_func=lambda item: ISSUE_LABELS[item],
            key=f"issues-{pair_id}-{version}-{group_name}",
            placeholder="Choose any that apply",
        )
        selected.extend(group_selected)
    return selected


def status_short(status: str) -> str:
    return STATUS_SHORT_LABELS.get(status, "[ ]")


def version_summary(row: dict[str, str | int | bool | None]) -> str:
    if row["winner_version"]:
        return f"w:v{row['winner_version']}"
    return f"v{row['latest_version']}"


def render_sidebar_queue_summary(pair_rows, visible_pair_ids, current_index: int) -> None:
    unreviewed = count_rows(pair_rows, "Needs review")
    redo = count_rows(pair_rows, "Redo queued")
    rebuilt = sum(1 for item in pair_rows if item["rebuilt"])

    st.sidebar.markdown("**Queue summary**")
    summary_cols = st.sidebar.columns(2)
    summary_cols[0].metric("Left", unreviewed)
    summary_cols[1].metric("Needs redo", redo)
    st.sidebar.caption(f"Rebuilt clips: {rebuilt}")
    st.sidebar.caption(f"Showing clip {current_index + 1} of {len(visible_pair_ids)} in this filter.")


def next_pair_needing_review(pair_rows, current_pair_id: str):
    pair_ids = [item["pair_id"] for item in pair_rows]
    if current_pair_id not in pair_ids:
        current_index = -1
    else:
        current_index = pair_ids.index(current_pair_id)

    ordered_rows = pair_rows[current_index + 1 :] + pair_rows[: current_index + 1]
    for item in ordered_rows:
        if item["status"] == "Needs review":
            return item["pair_id"]
    return None


def next_import_target_path(source_path: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    candidate = target_dir / source_path.name
    if not candidate.exists():
        return candidate

    stem = source_path.stem
    suffix = source_path.suffix
    index = 2
    while True:
        candidate = target_dir / f"{stem}_pool{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def next_pair_to_review(pair_rows, current_pair_id: str):
    pair_ids = [item["pair_id"] for item in pair_rows]
    if current_pair_id not in pair_ids:
        ordered_rows = pair_rows
    else:
        current_index = pair_ids.index(current_pair_id)
        ordered_rows = pair_rows[current_index + 1 :] + pair_rows[:current_index]

    for item in ordered_rows:
        if item["status"] == "Needs review":
            return item["pair_id"]
    return None


def set_selected_pair(pair_id: str) -> None:
    st.session_state.pending_selected_pair_choice = pair_id


def pair_label(pair_id: str) -> str:
    start_frame, end_frame = pair_id.split("_to_", 1)
    return f"{pair_id} | {start_frame} to {end_frame}"


if __name__ == "__main__":
    main()
