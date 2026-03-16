from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
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

from concat_videos import ordered_segment_files_for_pair_keys, stitch_pair_keys
from extend_image_judge import judge_available as local_judge_available
from extend_image_judge import judge_extension as run_local_extension_judge
from generate_all_videos import build_pairs_from_sequence, sort_key as natural_image_sort_key
from image_pair_prompts import get_pair_prompt
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

WORKFLOW_STEPS = [
    ("upload", "Upload Photos"),
    ("prepare", "Prepare Images"),
    ("sequence", "Build Sequence"),
    ("generate", "Generate Videos"),
    ("review", "Review & Fix"),
    ("export", "Export Movie"),
]
WORKFLOW_LABELS = dict(WORKFLOW_STEPS)

ROOT_DIR = Path(__file__).resolve().parent
OUTPAINTED_DIR = ROOT_DIR / "outpainted"
RAW_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
DEFAULT_EXTENSION_OUTPUT_DIR = "kling_test/manual_extends"
EXTEND_TAB_STATE_PATH = ROOT_DIR / "pipeline_runs" / "extend_tab_state.json"
BUILD_TAB_STATE_PATH = ROOT_DIR / "pipeline_runs" / "build_movie_state.json"
BUILD_JOB_DIR = ROOT_DIR / "pipeline_runs" / "build_jobs"
UI_STATE_PATH = ROOT_DIR / "pipeline_runs" / "ui_state.json"
EXTEND_TARGET_W = 5376
EXTEND_TARGET_H = 3024
EXTEND_IMAGE_MODEL = "gemini-3-pro-image-preview"
STORYBOARD_COMPONENT = components.declare_component(
    "movie_storyboard",
    path=str(ROOT_DIR / "components" / "storyboard"),
)


def main() -> None:
    st.set_page_config(
        page_title="AI Movie Studio",
        page_icon="&#127916;",
        layout="wide",
    )
    inject_styles()

    st.markdown(
        """
        <div class="hero-banner">
            <h1>AI Movie Studio</h1>
            <p>Turn your family photos into a cinematic movie. Upload, prepare, sequence, generate, review, and export — all in one place.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    review_notice = st.session_state.pop("review_notice", "")
    if review_notice:
        st.success(review_notice)

    run_id, status_filter, active_step = sidebar_controls()
    ensure_review_files(run_id)

    render_workflow_strip(active_step)

    if active_step == "upload":
        render_upload_tab()
    elif active_step == "prepare":
        render_prepare_tab()
    elif active_step == "sequence":
        render_build_movie_tab()
    elif active_step == "generate":
        render_generate_tab()
    elif active_step == "review":
        render_review_and_fix_tab(run_id, status_filter)
    elif active_step == "export":
        render_export_tab(run_id)
    else:
        render_upload_tab()

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


def normalize_ordered_images(saved_order: list[str], available_names: list[str], append_missing: bool = True) -> list[str]:
    available_set = set(available_names)
    ordered = [name for name in saved_order if name in available_set]
    if append_missing:
        ordered.extend(name for name in available_names if name not in ordered)
    return ordered


def active_sequence_pairs(ordered_names: list[str], disabled_pair_keys: set[str]) -> list[tuple[str, str, str]]:
    return [
        (start_name, end_name, pair_key)
        for start_name, end_name, pair_key in build_pairs_from_sequence(ordered_names)
        if pair_key not in disabled_pair_keys
    ]


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
    disabled_pair_keys: list[str],
    component_key: str,
) -> dict[str, list[str] | str] | None:
    return STORYBOARD_COMPONENT(
        items=items,
        selected_id=selected_id,
        disabled_pair_keys=disabled_pair_keys,
        key=component_key,
        default={
            "ordered_ids": [item["id"] for item in items],
            "selected_id": selected_id,
            "disabled_pair_keys": disabled_pair_keys,
        },
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


def load_build_tab_state() -> dict[str, object]:
    if not BUILD_TAB_STATE_PATH.exists():
        return {}
    try:
        return json.loads(BUILD_TAB_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_ui_state() -> dict[str, str]:
    if not UI_STATE_PATH.exists():
        return {}
    try:
        return json.loads(UI_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_ui_state(active_workflow_step: str) -> None:
    UI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    UI_STATE_PATH.write_text(
        json.dumps({"active_workflow_step": active_workflow_step}, indent=2),
        encoding="utf-8",
    )


def save_build_tab_state(
    source_folder: Path,
    ordered_images: list[str],
    selected_pair_keys: list[str],
    custom_order: bool,
    pool_folder: Path | None = None,
    disabled_pair_keys: list[str] | None = None,
    prompt_overrides: dict[str, str] | None = None,
    prompt_sources: dict[str, str] | None = None,
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
    if disabled_pair_keys:
        payload["disabled_pair_keys"] = disabled_pair_keys
    if prompt_overrides:
        payload["prompt_overrides"] = prompt_overrides
    if prompt_sources:
        payload["prompt_sources"] = prompt_sources
    BUILD_TAB_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_job_state_path(source_folder: Path) -> Path:
    BUILD_JOB_DIR.mkdir(parents=True, exist_ok=True)
    return BUILD_JOB_DIR / f"{folder_key_text(source_folder).replace('/', '__')}.json"


def save_build_job_state(source_folder: Path, payload: dict[str, object]) -> None:
    build_job_state_path(source_folder).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_build_job_state(source_folder: Path) -> dict[str, object]:
    path = build_job_state_path(source_folder)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


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
    api_key = os.getenv("PROMPT_LLM_API_KEY")
    if not api_key:
        raise RuntimeError("No prompt LLM API key found in .env")
    return genai.Client(api_key=api_key)


def normalize_prompt_text(text: str) -> str:
    return " ".join(text.strip().split())


def generate_build_pair_prompt_with_llm(
    pair_key: str,
    start_name: str,
    end_name: str,
    start_path: Path,
    end_path: Path,
    base_prompt: str,
    current_prompt: str,
    *,
    imaginative: bool = False,
) -> str | None:
    client = get_extend_api_client()
    if client is None:
        return None

    extra_goals = ""
    if imaginative:
        extra_goals = """
- keep the prompt grounded in the real stills, but make the transition more cinematic and imaginative
- prefer a clear visual handoff, reveal, reframing, or memory-like transition instead of a plain morph
- stay believable for Kling and avoid surreal invention unless it is clearly supported by the images
- do not lose the main identity, setting, or story continuity while making it more expressive
"""

    rewrite_request = f"""Create a Kling image-to-video prompt for pair {pair_key} by looking at the two attached stills.

Return only the final prompt text.

Goals:
- keep it concise and directly usable in Kling
- prefer 2 to 4 short sentences
- make the first sentence the camera move
- preserve subject identity, face, clothing, and pose continuity when relevant
- transition naturally from the start still to the end still
- keep the same setting and avoid inventing a new scene unless clearly implied by the stills
- use specific motion and continuity wording instead of abstract mood language
- analyze the attached images instead of paraphrasing the base prompt
- mention the most important real visual continuity cues from the stills when they matter
{extra_goals}

Start still: {start_name}
End still: {end_name}

Base prompt:
{base_prompt}

Current working prompt:
{current_prompt}
"""

    try:
        start_image = ImageOps.exif_transpose(Image.open(start_path)).convert("RGB")
        end_image = ImageOps.exif_transpose(Image.open(end_path)).convert("RGB")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[rewrite_request, start_image, end_image],
        )
    except Exception:
        return None

    text = getattr(response, "text", None)
    if not text:
        return None
    normalized = normalize_prompt_text(text)
    return normalized or None


def build_pair_prompt_brief(
    pair_key: str,
    start_name: str,
    end_name: str,
    base_prompt: str,
    current_prompt: str,
) -> str:
    return f"""Create a Kling image-to-video prompt for pair {pair_key}.

Return only the final prompt text.

Requirements:
- keep it concise and directly usable in Kling
- use 2 to 4 short sentences
- make the first sentence the camera move
- preserve the same person, face, clothing, and pose continuity when relevant
- transition naturally from the start still to the end still
- keep the same setting and avoid inventing a new scene unless clearly implied by the stills

Start still: {start_name}
End still: {end_name}
Base prompt: {base_prompt}
Current working prompt: {current_prompt}
"""


def build_pair_prompt_codex_request(
    pair_key: str,
    start_name: str,
    end_name: str,
    start_path: Path,
    end_path: Path,
    base_prompt: str,
    current_prompt: str,
) -> str:
    return f"""Create a Kling image-to-video prompt for pair {pair_key}.

Return only the final prompt text.

Look at the two attached stills and write the prompt from the actual images, not just from the text prompt below.

Requirements:
- keep it concise and directly usable in Kling
- use 2 to 4 short sentences
- make the first sentence the camera move
- preserve the same person, face, clothing, and pose continuity when relevant
- transition naturally from the start still to the end still
- keep the same setting and avoid inventing a new scene unless clearly implied by the stills

Start still path: {start_path}
End still path: {end_path}
Start still name: {start_name}
End still name: {end_name}
Base prompt: {base_prompt}
Current working prompt: {current_prompt}
"""


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
    nav_cols = st.columns([1, 1, 1.2, 1.1] if include_picker else [1, 1, 1.2, 1.2], gap="small")
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
    if include_picker:
        if nav_cols[3].button(
            "Jump to compare",
            use_container_width=True,
            key=f"{active_key}::jump_compare",
        ):
            st.session_state["pending_extend_scroll_anchor"] = "extend-compare-anchor"
            st.rerun()
        return st.session_state[active_key]

    nav_cols[3].caption("Use these buttons while comparing to move without scrolling up.")
    return st.session_state[active_key]


def render_extension_thumbnail_board(
    visible_names: list[str],
    browser_rows: list[dict[str, str]],
    source_lookup: dict[str, Path],
    active_key: str,
) -> None:
    status_lookup = {row["image"]: row["status"] for row in browser_rows}
    with st.expander("Thumbnail browser", expanded=True):
        st.caption("Click a still to make it active. The compare view below updates from the active still.")

        columns_per_row = 6
        for row_start in range(0, len(visible_names), columns_per_row):
            row_names = visible_names[row_start : row_start + columns_per_row]
            tile_cols = st.columns(len(row_names), gap="small")
            for tile_col, image_name in zip(tile_cols, row_names):
                is_active = st.session_state[active_key] == image_name
                status_text = status_lookup.get(image_name, "")
                button_label = "Current" if is_active else "Select"
                with tile_col:
                    st.markdown(
                        f"<div class='extend-thumb-title'>{image_name}</div>",
                        unsafe_allow_html=True,
                    )
                    st.image(
                        load_display_image_bytes(
                            str(source_lookup[image_name]),
                            260,
                            image_cache_key(source_lookup[image_name]),
                        ),
                        use_container_width=True,
                    )
                    if st.button(
                        button_label,
                        key=f"{active_key}::thumb::{image_name}",
                        use_container_width=True,
                        disabled=is_active,
                    ):
                        st.session_state[active_key] = image_name
                        st.rerun()
                    st.caption(status_text)


def render_upload_tab() -> None:
    st.subheader("Upload Photos")
    st.caption("Start here. Add your family photos to a project folder. These raw images will be prepared and extended in the next step.")

    target_dir = OUTPAINTED_DIR.parent
    upload_folder_key = "upload_target_folder"
    if upload_folder_key not in st.session_state:
        st.session_state[upload_folder_key] = target_dir

    existing_images = sorted(
        [
            path
            for path in target_dir.iterdir()
            if path.is_file() and path.suffix.lower() in RAW_IMAGE_EXTENSIONS
        ],
        key=lambda p: p.name.lower(),
    ) if target_dir.exists() else []

    summary_cols = st.columns(3, gap="small")
    summary_cols[0].markdown(
        f"<div class='extend-summary-card'><span>Project folder</span><strong>{relative_folder_label(target_dir)}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[1].markdown(
        f"<div class='extend-summary-card'><span>Photos loaded</span><strong>{len(existing_images)}</strong></div>",
        unsafe_allow_html=True,
    )
    outpainted_count = len(list(OUTPAINTED_DIR.glob("*.jpg"))) + len(list(OUTPAINTED_DIR.glob("*.jpeg"))) + len(list(OUTPAINTED_DIR.glob("*.png"))) if OUTPAINTED_DIR.exists() else 0
    summary_cols[2].markdown(
        f"<div class='extend-summary-card'><span>Already normalized (4:3)</span><strong>{outpainted_count}</strong></div>",
        unsafe_allow_html=True,
    )

    render_next_action_card(
        "How it works",
        "Upload your photos here, then move to Prepare Images to normalize them to a consistent format for video generation.",
    )

    st.markdown(
        """
        <div class="upload-zone">
            <h4>Drop your photos below</h4>
            <p>Supported formats: JPG, JPEG, PNG</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    uploaded_files = st.file_uploader(
        "Upload photos",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="upload_photos_uploader",
        label_visibility="collapsed",
    )
    if uploaded_files:
        target_dir.mkdir(parents=True, exist_ok=True)
        saved_count = 0
        for uploaded_file in uploaded_files:
            dest = target_dir / uploaded_file.name
            if not dest.exists():
                dest.write_bytes(uploaded_file.getvalue())
                saved_count += 1
        if saved_count > 0:
            st.success(f"Saved {saved_count} new photo(s) to {relative_folder_label(target_dir)}.")
            st.rerun()
        else:
            st.info("All uploaded files already exist in the project folder.")

    folder_actions = st.columns([1, 1, 2], gap="small")
    if folder_actions[0].button("Open project folder", use_container_width=True, key="upload_open_folder"):
        open_folder_in_windows(target_dir)
    if folder_actions[1].button("Refresh", use_container_width=True, key="upload_refresh"):
        st.rerun()

    if not existing_images:
        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-icon">&#128247;</div>
                <h3>No photos yet</h3>
                <p>Upload your family photos using the uploader above, or place them directly in the project folder.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(f"**Photo gallery** ({len(existing_images)} images)")
    thumb_cols = st.columns(6, gap="small")
    for index, image_path in enumerate(existing_images):
        with thumb_cols[index % 6]:
            st.image(
                load_display_image_bytes(str(image_path), 300, image_cache_key(image_path)),
                caption=image_path.name,
                use_container_width=True,
            )

    if len(existing_images) >= 2:
        st.markdown(
            """
            <div class="success-banner">
                <div class="success-icon">&#9989;</div>
                <div>
                    <div class="success-text">Ready for the next step</div>
                    <div class="success-detail">Click "Prepare Images" in the workflow above to normalize your photos to a consistent format.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_prepare_tab() -> None:
    st.subheader("Prepare Images")
    st.caption("Normalize your photos to a consistent format for AI video generation. Two phases: first 4:3, then 16:9.")

    source_dir = ROOT_DIR
    raw_images = sorted(
        [
            path for path in source_dir.iterdir()
            if path.is_file() and path.suffix.lower() in RAW_IMAGE_EXTENSIONS
        ],
        key=lambda p: p.name.lower(),
    ) if source_dir.exists() else []
    outpainted_images = sorted(
        [
            path for path in OUTPAINTED_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in RAW_IMAGE_EXTENSIONS
        ],
        key=lambda p: p.name.lower(),
    ) if OUTPAINTED_DIR.exists() else []
    kling_dir = ROOT_DIR / "kling_test"
    extended_images = sorted(
        [
            path for path in kling_dir.iterdir()
            if path.is_file() and path.suffix.lower() in RAW_IMAGE_EXTENSIONS
        ],
        key=lambda p: p.name.lower(),
    ) if kling_dir.exists() else []

    summary_cols = st.columns(4, gap="small")
    summary_cols[0].markdown(
        f"<div class='extend-summary-card'><span>Source photos</span><strong>{len(raw_images)}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[1].markdown(
        f"<div class='extend-summary-card'><span>Normalized (4:3)</span><strong>{len(outpainted_images)}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[2].markdown(
        f"<div class='extend-summary-card'><span>Extended (16:9)</span><strong>{len(extended_images)}</strong></div>",
        unsafe_allow_html=True,
    )
    phase_a_done = len(outpainted_images) >= len(raw_images) if raw_images else False
    phase_b_done = len(extended_images) >= len(outpainted_images) if outpainted_images else False
    overall_status = "All done" if phase_a_done and phase_b_done else "In progress" if outpainted_images or extended_images else "Not started"
    summary_cols[3].markdown(
        f"<div class='extend-summary-card'><span>Status</span><strong>{overall_status}</strong></div>",
        unsafe_allow_html=True,
    )

    # --- Phase A: Normalize to 4:3 ---
    st.markdown(
        """
        <div class="phase-header">
            <div class="phase-badge">Phase A</div>
            <div class="phase-title">Normalize to 4:3 aspect ratio</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Uses Gemini AI to intelligently extend your photos to a consistent 4:3 format while preserving faces and subjects.")

    if not raw_images:
        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-icon">&#128247;</div>
                <h3>No source photos found</h3>
                <p>Upload your family photos in the Upload Photos step first, then come back here to normalize them.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        normalize_progress = len(outpainted_images) / len(raw_images) if raw_images else 0
        st.progress(min(normalize_progress, 1.0), text=f"{len(outpainted_images)} of {len(raw_images)} normalized")

        normalize_cols = st.columns([1.2, 1, 1], gap="small")
        if normalize_cols[0].button(
            "Run 4:3 normalize",
            use_container_width=True,
            type="primary",
            key="prepare_run_normalize",
        ):
            creation_flags = 0
            if os.name == "nt":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            subprocess.Popen(
                [sys.executable, str(ROOT_DIR / "outpaint_images.py")],
                cwd=str(ROOT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            st.success("Started normalization process in the background. Click Refresh to check progress.")
        if normalize_cols[1].button("Open outpainted folder", use_container_width=True, key="prepare_open_outpainted"):
            OUTPAINTED_DIR.mkdir(parents=True, exist_ok=True)
            open_folder_in_windows(OUTPAINTED_DIR)
        if normalize_cols[2].button("Refresh", use_container_width=True, key="prepare_refresh_a"):
            st.rerun()

    # --- Phase B: Extend to 16:9 ---
    st.markdown(
        """
        <div class="phase-header">
            <div class="phase-badge">Phase B</div>
            <div class="phase-title">Extend to 16:9 cinematic format</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Expand 4:3 images to 16:9 widescreen for Kling video generation. Use the extension browser below to review and adjust each image.")

    if not outpainted_images:
        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-icon">&#128248;</div>
                <h3>No normalized images yet</h3>
                <p>Complete Phase A above first. Once your photos are normalized to 4:3, you can extend them to 16:9 here.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        extend_progress = len(extended_images) / len(outpainted_images) if outpainted_images else 0
        st.progress(min(extend_progress, 1.0), text=f"{len(extended_images)} of {len(outpainted_images)} extended")

        st.caption("For detailed per-image extension controls, use the extension browser below.")

    render_extend_images_tab()

    if phase_a_done and phase_b_done:
        st.markdown(
            """
            <div class="success-banner">
                <div class="success-icon">&#9989;</div>
                <div>
                    <div class="success-text">All images prepared</div>
                    <div class="success-detail">Move to Build Sequence to arrange your photos and set up video transitions.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_workflow_strip(active_step: str) -> None:
    display_labels = {
        "upload": "Upload Photos",
        "prepare": "Prepare Images",
        "sequence": "Build Sequence",
        "generate": "Generate Videos",
        "review": "Review & Fix",
        "export": "Export Movie",
    }
    button_cols = st.columns(len(WORKFLOW_STEPS), gap="small")
    for step_number, (column, (step_key, _)) in enumerate(zip(button_cols, WORKFLOW_STEPS), start=1):
        label = f"{step_number}. {display_labels[step_key]}"
        if column.button(
            label,
            use_container_width=True,
            key=f"workflow_button::{step_key}",
            type="primary" if step_key == active_step else "secondary",
        ):
            if st.session_state.get("active_workflow_step") != step_key:
                st.session_state["pending_workflow_step"] = step_key
                st.rerun()


def render_next_action_card(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="next-action-card">
          <span>{title}</span>
          <strong>{body}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


def start_build_generation_job(source_folder: Path, job_payload: dict[str, object]) -> None:
    request_path = build_job_state_path(source_folder)
    request_path.write_text(json.dumps(job_payload, indent=2), encoding="utf-8")

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT_DIR / "generate_all_videos.py"),
            "--request",
            str(request_path),
        ],
        cwd=str(ROOT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    job_payload["pid"] = process.pid
    save_build_job_state(source_folder, job_payload)


def stop_build_generation_job(job_state: dict[str, object]) -> bool:
    pid = job_state.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        os.kill(pid, 15)
        return True
    except OSError:
        return False


def render_build_generation_progress(source_folder: Path, job_state: dict[str, object], status_path: str) -> None:
    selected_pair_keys = [
        str(item)
        for item in job_state.get("selected_pair_keys", [])
        if isinstance(item, str)
    ]
    if not selected_pair_keys:
        return

    try:
        status_data = json.loads(Path(status_path).read_text(encoding="utf-8")) if Path(status_path).exists() else {}
    except (OSError, json.JSONDecodeError):
        status_data = {}

    relevant_statuses = [
        (pair_key, status_data.get(pair_key, {}))
        for pair_key in selected_pair_keys
    ]
    done_items = [
        (pair_key, item)
        for pair_key, item in relevant_statuses
        if isinstance(item, dict) and item.get("result") in {"ok", "submit_fail", "poll_fail"}
    ]
    ok_count = sum(1 for _, item in done_items if item.get("result") == "ok")
    failed_count = sum(1 for _, item in done_items if item.get("result") != "ok")
    remaining_count = len(selected_pair_keys) - len(done_items)
    last_finished_pair = done_items[-1][0] if done_items else "-"
    is_terminal = remaining_count == 0
    total_count = len(selected_pair_keys)
    finished_count = len(done_items)
    progress_value = 0.0 if total_count == 0 else finished_count / total_count
    progress_label = f"{finished_count} of {total_count} pair(s) finished"
    if failed_count:
        progress_label += f" ({failed_count} failed)"
    auto_refresh_key = f"build_auto_refresh::{folder_key_text(source_folder)}"
    if auto_refresh_key not in st.session_state:
        st.session_state[auto_refresh_key] = False

    st.markdown("**Latest build run**")
    st.progress(progress_value, text=progress_label)
    progress_cols = st.columns(4, gap="small")
    progress_cols[0].markdown(
        f"<div class='extend-summary-card'><span>Selected</span><strong>{len(selected_pair_keys)}</strong></div>",
        unsafe_allow_html=True,
    )
    progress_cols[1].markdown(
        f"<div class='extend-summary-card'><span>Completed</span><strong>{ok_count}</strong></div>",
        unsafe_allow_html=True,
    )
    progress_cols[2].markdown(
        f"<div class='extend-summary-card'><span>Failed</span><strong>{failed_count}</strong></div>",
        unsafe_allow_html=True,
    )
    progress_cols[3].markdown(
        f"<div class='extend-summary-card'><span>Remaining</span><strong>{remaining_count}</strong></div>",
        unsafe_allow_html=True,
    )

    detail_cols = st.columns([1.3, 0.9, 0.9, 1], gap="small")
    detail_cols[0].caption(f"Last finished pair: {last_finished_pair}")
    if detail_cols[1].button("Refresh progress", use_container_width=True, key=f"build_refresh_progress::{folder_key_text(source_folder)}"):
        st.rerun()
    if detail_cols[2].button(
        "Stop current run",
        use_container_width=True,
        key=f"build_stop_progress::{folder_key_text(source_folder)}",
        disabled=is_terminal,
    ):
        if stop_build_generation_job(job_state):
            job_state["stopped"] = True
            save_build_job_state(source_folder, job_state)
            st.session_state["build_generation_notice"] = "Requested stop for the current Kling build run."
        else:
            st.session_state["build_generation_notice"] = "Could not stop the current Kling build run."
        st.rerun()
    if detail_cols[3].button("Open videos folder", use_container_width=True, key=f"build_open_videos::{folder_key_text(source_folder)}"):
        open_folder_in_windows(Path(str(job_state.get("video_dir", Path(status_path).parent))))
    st.checkbox(
        "Auto-refresh every 5 seconds",
        key=auto_refresh_key,
        disabled=is_terminal,
    )

    if is_terminal:
        st.success("This build run has reached a terminal state for all selected pairs.")
    elif job_state.get("stopped"):
        st.warning("This build run was stopped before all selected pairs finished.")
    else:
        st.info("The Kling batch is running in the background. Use Refresh progress to check new completions.")

    if st.session_state.get(auto_refresh_key) and not is_terminal and not job_state.get("stopped"):
        components.html(
            """
            <script>
            setTimeout(function () {
              window.parent.location.reload();
            }, 5000);
            </script>
            """,
            height=0,
        )


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
        source_cols = st.columns([2.2, 0.5, 0.45], gap="small")
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
        output_cols = st.columns([0.95, 1.25, 0.5, 0.45], gap="small")
        selected_output_preset = output_cols[0].selectbox(
            "Output folder preset",
            options=output_preset_options,
            key=output_preset_key,
            label_visibility="collapsed",
            help="Pick an existing folder quickly, or switch to Custom and type any project-relative output path.",
        )
        if selected_output_preset != "Custom...":
            st.session_state[output_text_key] = selected_output_preset

        output_folder_text = output_cols[1].text_input(
            "Output folder",
            key=output_text_key,
            label_visibility="collapsed",
            help="Images are treated as the same item only when the same filename already exists in this chosen output folder. You can type any relative project path here.",
        )
        if output_cols[2].button("Browse...", use_container_width=True, key="browse_output_folder"):
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
        if output_cols[3].button("Open", use_container_width=True, key="open_output_folder"):
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
    render_next_action_card(
        "Next action",
        "Pick one still, check the compare view, then run Gemini API or save a manual result.",
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
    render_extension_thumbnail_board(
        visible_names,
        browser_rows,
        source_lookup,
        active_key,
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

    compare_controls = st.columns([1.2, 1, 1], gap="small")
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
    st.caption("Use left/right buttons above to move quickly through the folder.")
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
    st.subheader("Build Sequence")
    st.caption("Arrange your prepared 16:9 images in the order you want them to appear in the final movie. Each consecutive pair becomes one video transition.")
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
        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-icon">&#127910;</div>
                <h3>No images found</h3>
                <p>This folder has no image files yet. Go back to Prepare Images to extend your photos to 16:9 format, or select a different source folder above.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    available_names = [path.name for path in source_paths]
    source_lookup = {path.name: path for path in source_paths}
    ordered_state_key = f"build_ordered_images::{folder_key_text(selected_folder)}"
    custom_order_key = f"build_custom_order::{folder_key_text(selected_folder)}"
    prompt_overrides_key = f"build_prompt_overrides::{folder_key_text(selected_folder)}"
    prompt_sources_key = f"build_prompt_sources::{folder_key_text(selected_folder)}"
    saved_order = saved_state.get("ordered_images", [])
    saved_folder_label = str(saved_state.get("source_folder", ""))
    saved_custom_order = bool(saved_state.get("custom_order", False))
    saved_disabled_pair_keys = saved_state.get("disabled_pair_keys", [])
    saved_prompt_overrides = saved_state.get("prompt_overrides", {})
    saved_prompt_sources = saved_state.get("prompt_sources", {})
    use_saved_order = (
        saved_folder_label == relative_folder_label(selected_folder)
        and saved_custom_order
        and isinstance(saved_order, list)
    )
    if custom_order_key not in st.session_state:
        st.session_state[custom_order_key] = use_saved_order
        st.session_state[ordered_state_key] = normalize_ordered_images(
            saved_order if use_saved_order else [],
            available_names,
            append_missing=not use_saved_order,
        )
    elif ordered_state_key not in st.session_state:
        st.session_state[ordered_state_key] = normalize_ordered_images(
            saved_order if use_saved_order else [],
            available_names,
            append_missing=not use_saved_order,
        )
    else:
        st.session_state[ordered_state_key] = normalize_ordered_images(
            st.session_state[ordered_state_key],
            available_names,
            append_missing=not st.session_state[custom_order_key],
        )
    ordered_names = st.session_state[ordered_state_key]
    disabled_pairs_key = f"build_disabled_pairs::{folder_key_text(selected_folder)}"
    if disabled_pairs_key not in st.session_state:
        if (
            saved_folder_label == relative_folder_label(selected_folder)
            and isinstance(saved_disabled_pair_keys, list)
        ):
            st.session_state[disabled_pairs_key] = [str(item) for item in saved_disabled_pair_keys if isinstance(item, str)]
        else:
            st.session_state[disabled_pairs_key] = []
    disabled_pair_keys = {
        pair_key
        for pair_key in st.session_state[disabled_pairs_key]
        if isinstance(pair_key, str)
    }
    st.session_state[disabled_pairs_key] = sorted(disabled_pair_keys)
    if (
        saved_folder_label == relative_folder_label(selected_folder)
        and isinstance(saved_prompt_overrides, dict)
    ):
        st.session_state[prompt_overrides_key] = {
            str(key): str(value)
            for key, value in saved_prompt_overrides.items()
            if isinstance(key, str) and isinstance(value, str)
        }
    elif prompt_overrides_key not in st.session_state:
        st.session_state[prompt_overrides_key] = {}
    if (
        saved_folder_label == relative_folder_label(selected_folder)
        and isinstance(saved_prompt_sources, dict)
    ):
        st.session_state[prompt_sources_key] = {
            str(key): str(value)
            for key, value in saved_prompt_sources.items()
            if isinstance(key, str) and isinstance(value, str)
        }
    elif prompt_sources_key not in st.session_state:
        st.session_state[prompt_sources_key] = {}
    prompt_overrides = st.session_state[prompt_overrides_key]
    prompt_sources = st.session_state[prompt_sources_key]

    pending_import_key = f"build_pending_import::{folder_key_text(selected_folder)}"
    pending_import = st.session_state.pop(pending_import_key, None)
    if isinstance(pending_import, dict):
        imported_names = [
            str(name)
            for name in pending_import.get("names", [])
            if isinstance(name, str) and name in available_names
        ]
        if imported_names:
            ordered_names = [name for name in ordered_names if name not in imported_names]
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
    pending_import_notice = st.session_state.pop(
        f"build_pending_import_notice::{folder_key_text(selected_folder)}",
        "",
    )
    pending_scroll_anchor = st.session_state.pop(
        f"build_pending_scroll_anchor::{folder_key_text(selected_folder)}",
        "",
    )

    current_image_key = f"build_current_image::{folder_key_text(selected_folder)}"
    if current_image_key not in st.session_state or st.session_state[current_image_key] not in ordered_names:
        st.session_state[current_image_key] = ordered_names[0]

    if pending_import_notice:
        st.success(pending_import_notice)

    st.markdown("<div id='build-storyboard-anchor'></div>", unsafe_allow_html=True)
    if pending_scroll_anchor:
        render_extend_scroll_restore(pending_scroll_anchor)

    st.markdown("**Storyboard**")
    st.caption("Drag thumbnails to reorder your movie sequence. Click a thumbnail to select it. Each pair of consecutive images becomes one video transition.")
    storyboard_items = [
        {
            "id": name,
            "name": name,
            "thumb": load_compare_data_uri(str(source_lookup[name]), 320, image_cache_key(source_lookup[name])),
            "outgoing_pair_key": (
                f"{Path(name).stem}_to_{Path(ordered_names[index + 1]).stem}"
                if index < len(ordered_names) - 1
                else ""
            ),
            "outgoing_enabled": (
                index < len(ordered_names) - 1
                and f"{Path(name).stem}_to_{Path(ordered_names[index + 1]).stem}" not in disabled_pair_keys
            ),
            "next_name": ordered_names[index + 1] if index < len(ordered_names) - 1 else "",
        }
        for index, name in enumerate(ordered_names)
    ]
    storyboard_value = render_storyboard_component(
        storyboard_items,
        st.session_state[current_image_key],
        st.session_state[disabled_pairs_key],
        component_key=f"build_storyboard::{folder_key_text(selected_folder)}",
    )
    if isinstance(storyboard_value, dict):
        new_order = storyboard_value.get("ordered_ids", [])
        if isinstance(new_order, list):
            normalized_order = normalize_ordered_images(
                [str(name) for name in new_order],
                available_names,
                append_missing=False,
            )
            if normalized_order != ordered_names:
                st.session_state[ordered_state_key] = normalized_order
                ordered_names = normalized_order
                st.session_state[custom_order_key] = True
                valid_disabled_pairs = {
                    pair_key
                    for _, _, pair_key in build_pairs_from_sequence(ordered_names)
                }
                st.session_state[disabled_pairs_key] = sorted(
                    pair_key for pair_key in st.session_state[disabled_pairs_key] if pair_key in valid_disabled_pairs
                )
        removed_name = str(storyboard_value.get("removed_id", "")).strip()
        if removed_name:
            if removed_name in ordered_names and len(ordered_names) > 2:
                removed_index = ordered_names.index(removed_name)
                ordered_names = [name for name in ordered_names if name != removed_name]
                st.session_state[ordered_state_key] = ordered_names
                st.session_state[custom_order_key] = True
                valid_disabled_pairs = {
                    pair_key
                    for _, _, pair_key in build_pairs_from_sequence(ordered_names)
                }
                st.session_state[disabled_pairs_key] = sorted(
                    pair_key for pair_key in st.session_state[disabled_pairs_key] if pair_key in valid_disabled_pairs
                )
                if st.session_state[current_image_key] == removed_name:
                    fallback_index = max(0, min(removed_index, len(ordered_names) - 1))
                    st.session_state[current_image_key] = ordered_names[fallback_index]
                st.rerun()
        new_disabled_pairs = storyboard_value.get("disabled_pair_keys", [])
        if isinstance(new_disabled_pairs, list):
            normalized_disabled_pairs = sorted(
                pair_key
                for pair_key in {str(item) for item in new_disabled_pairs}
                if pair_key
            )
            if normalized_disabled_pairs != st.session_state[disabled_pairs_key]:
                st.session_state[disabled_pairs_key] = normalized_disabled_pairs
                st.rerun()
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
            st.session_state[ordered_state_key] = normalize_ordered_images([], available_names, append_missing=True)
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
            pending_pool_notice = st.session_state.pop("pending_build_pool_notice", "")
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
                if pending_pool_notice:
                    st.warning(pending_pool_notice)
                pool_folder_key = "build_pool_folder"
                if pool_folder_key not in st.session_state or st.session_state[pool_folder_key] not in pool_folders:
                    st.session_state[pool_folder_key] = initial_pool_folder
                if pending_pool_folder is not None and pending_pool_folder in pool_folders:
                    st.session_state[pool_folder_key] = pending_pool_folder

                pool_cols = st.columns([1.55, 0.5, 0.45], gap="small")
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
                        if picked_pool.resolve() == selected_folder.resolve():
                            st.session_state["pending_build_pool_notice"] = (
                                "That folder is already the active build folder. Pick a different pool folder to import from."
                            )
                        else:
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
                        checked = str(pool_path) in current_pool_selection
                        if st.checkbox(
                            "Select",
                            value=checked,
                            key=f"build_pool_pick::{folder_key_text(selected_folder)}::{folder_key_text(pool_folder)}::{folder_key_text(pool_path)}",
                        ):
                            current_pool_selection.add(str(pool_path))
                        else:
                            current_pool_selection.discard(str(pool_path))
                        st.image(
                            load_display_image_bytes(str(pool_path), 320, image_cache_key(pool_path)),
                            caption=pool_path.name,
                            use_container_width=True,
                        )
                        st.caption(relative_folder_label(pool_path.parent))
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
                    st.session_state[f"build_pending_import_notice::{folder_key_text(selected_folder)}"] = (
                        f"Added {len(imported_names)} image(s) after {current_name}."
                    )
                    st.session_state[f"build_pending_scroll_anchor::{folder_key_text(selected_folder)}"] = "build-storyboard-anchor"
                    st.session_state[selected_pool_key] = []
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
                    st.session_state[f"build_pending_import_notice::{folder_key_text(selected_folder)}"] = (
                        f"Added {len(imported_names)} image(s) to the end of the storyboard."
                    )
                    st.session_state[f"build_pending_scroll_anchor::{folder_key_text(selected_folder)}"] = "build-storyboard-anchor"
                    st.session_state[selected_pool_key] = []
                    st.rerun()

    folder_prompt_label = relative_folder_label(selected_folder)
    pair_rows = []
    sequence_pairs = active_sequence_pairs(ordered_names, disabled_pair_keys)
    for start_name, end_name, pair_key in sequence_pairs:
        base_prompt = get_pair_prompt(pair_key, folder_prompt_label)
        prompt_override = prompt_overrides.get(pair_key, "")
        prompt_source = prompt_sources.get(pair_key, "default")
        pair_rows.append(
            {
                "pair_key": pair_key,
                "start": start_name,
                "end": end_name,
                "base_prompt": base_prompt,
                "prompt": prompt_override or base_prompt,
                "prompt_source": prompt_source,
            }
        )
    suggested_preview_key = pair_rows[min(current_index, len(pair_rows) - 1)]["pair_key"] if pair_rows else ""

    selected_pairs_key = f"build_selected_pairs::{folder_key_text(selected_folder)}"
    has_saved_pair_keys = "selected_pair_keys" in saved_state
    saved_pair_keys = saved_state.get("selected_pair_keys", [])
    default_pair_keys = [row["pair_key"] for row in pair_rows]
    if selected_pairs_key not in st.session_state:
        if has_saved_pair_keys and isinstance(saved_pair_keys, list):
            saved_set = set(saved_pair_keys)
            st.session_state[selected_pairs_key] = [
                row["pair_key"] for row in pair_rows if row["pair_key"] in saved_set
            ]
        else:
            st.session_state[selected_pairs_key] = default_pair_keys
    else:
        current_selected = set(st.session_state[selected_pairs_key])
        st.session_state[selected_pairs_key] = [
            row["pair_key"] for row in pair_rows if row["pair_key"] in current_selected
        ]

    save_build_tab_state(
        selected_folder,
        ordered_names,
        st.session_state[selected_pairs_key],
        st.session_state[custom_order_key],
        st.session_state.get("build_pool_folder"),
        st.session_state[disabled_pairs_key],
        prompt_overrides,
        prompt_sources,
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
    existing_segments = set(ordered_segment_files_for_pair_keys([row["pair_key"] for row in pair_rows], os.path.join(selected_folder, "videos")))
    summary_cols[3].markdown(
        f"<div class='extend-summary-card'><span>Segments ready</span><strong>{len(existing_segments)}</strong></div>",
        unsafe_allow_html=True,
    )
    render_next_action_card(
        "Next action",
        "Arrange your photos in order, preview the video transitions, then generate clips. When all clips are ready, move to Review.",
    )

    st.markdown("**Pair preview**")
    if not pair_rows:
        st.info("No active transitions right now. Turn at least one bridge back on in the storyboard to generate or stitch clips.")
        save_build_tab_state(
            selected_folder,
            ordered_names,
            [],
            st.session_state[custom_order_key],
            st.session_state.get("build_pool_folder"),
            st.session_state[disabled_pairs_key],
            prompt_overrides,
            prompt_sources,
        )
        return
    pair_keys = [row["pair_key"] for row in pair_rows]
    missing_pair_keys = [
        row["pair_key"]
        for row in pair_rows
        if f"seg_{row['pair_key']}.mp4" not in existing_segments
    ]
    existing_pair_keys = [pair_key for pair_key in pair_keys if pair_key not in missing_pair_keys]
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
        save_build_tab_state(selected_folder, ordered_names, st.session_state[selected_pairs_key], st.session_state[custom_order_key], st.session_state.get("build_pool_folder"), st.session_state[disabled_pairs_key], prompt_overrides, prompt_sources)
        st.rerun()
    if pair_action_cols[1].button("Only missing segments", use_container_width=True, key=f"build_select_missing::{folder_key_text(selected_folder)}"):
        st.session_state[selected_pairs_key] = missing_pair_keys or pair_keys
        save_build_tab_state(selected_folder, ordered_names, st.session_state[selected_pairs_key], st.session_state[custom_order_key], st.session_state.get("build_pool_folder"), st.session_state[disabled_pairs_key], prompt_overrides, prompt_sources)
        st.rerun()
    if pair_action_cols[2].button("Clear selection", use_container_width=True, key=f"build_clear_pairs::{folder_key_text(selected_folder)}"):
        st.session_state[selected_pairs_key] = []
        save_build_tab_state(selected_folder, ordered_names, st.session_state[selected_pairs_key], st.session_state[custom_order_key], st.session_state.get("build_pool_folder"), st.session_state[disabled_pairs_key], prompt_overrides, prompt_sources)
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
        st.session_state[disabled_pairs_key],
        prompt_overrides,
        prompt_sources,
    )

    preview_key = f"build_preview_pair::{folder_key_text(selected_folder)}"
    preview_options = [row["pair_key"] for row in pair_rows]
    if preview_key not in st.session_state or st.session_state[preview_key] not in preview_options:
        st.session_state[preview_key] = suggested_preview_key or preview_options[0]
    preview_index = preview_options.index(st.session_state[preview_key]) if preview_options else 0
    preview_action_cols = st.columns(4, gap="small")
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
    prompt_widget_key = f"build_prompt_preview::{folder_key_text(selected_folder)}::{preview_pair_key}"
    pending_prompt_key = f"build_pending_prompt::{folder_key_text(selected_folder)}::{preview_pair_key}"
    prompt_sync_key = f"build_prompt_sync::{folder_key_text(selected_folder)}"
    pending_prompt = st.session_state.pop(pending_prompt_key, None)
    source_prompt_text = preview_row["prompt"]
    prompt_sync_signature = f"{preview_pair_key}::{source_prompt_text}"
    if pending_prompt is not None:
        st.session_state[prompt_widget_key] = pending_prompt
        st.session_state[prompt_sync_key] = f"{preview_pair_key}::{pending_prompt}"
    elif st.session_state.get(prompt_sync_key) != prompt_sync_signature:
        st.session_state[prompt_widget_key] = source_prompt_text
        st.session_state[prompt_sync_key] = prompt_sync_signature

    prompt_source_label = {
        "default": "Default library prompt",
        "manual": "Manual edit",
        "gemini": "Gemini rewrite",
        "gemini_cinematic": "Gemini cinematic rewrite",
    }.get(preview_row["prompt_source"], "Custom prompt")
    st.caption(
        f"Prompt source: {prompt_source_label}. The prompt box below is the exact text Kling will use for this pair."
    )
    prompt_text = st.text_area(
        "Prompt for this pair",
        height=140,
        key=prompt_widget_key,
    )
    normalized_default_prompt = normalize_prompt_text(preview_row["base_prompt"])
    normalized_previous_override = normalize_prompt_text(prompt_overrides.get(preview_pair_key, ""))
    normalized_prompt_text = normalize_prompt_text(prompt_text)
    if normalized_prompt_text and normalized_prompt_text != normalized_default_prompt:
        prompt_overrides[preview_pair_key] = normalized_prompt_text
        if normalized_previous_override == normalized_prompt_text:
            prompt_sources[preview_pair_key] = prompt_sources.get(preview_pair_key, "manual")
        else:
            prompt_sources[preview_pair_key] = "manual"
    else:
        prompt_overrides.pop(preview_pair_key, None)
        prompt_sources.pop(preview_pair_key, None)

    helper_mode_key = f"build_prompt_helper_mode::{folder_key_text(selected_folder)}::{preview_pair_key}"
    helper_pair_key = f"build_prompt_helper_pair::{folder_key_text(selected_folder)}"
    if st.session_state.get(helper_pair_key) != preview_pair_key:
        st.session_state[helper_pair_key] = preview_pair_key
        st.session_state[helper_mode_key] = ""
    helper_mode = st.session_state.get(helper_mode_key, "")
    prompt_action_cols = st.columns(5, gap="small")
    if prompt_action_cols[0].button(
        "Generate with Gemini",
        use_container_width=True,
        key=f"build_generate_prompt::{folder_key_text(selected_folder)}::{preview_pair_key}",
    ):
        generated_prompt = generate_build_pair_prompt_with_llm(
            preview_pair_key,
            preview_row["start"],
            preview_row["end"],
            source_lookup[preview_row["start"]],
            source_lookup[preview_row["end"]],
            preview_row["base_prompt"],
            normalized_prompt_text or preview_row["base_prompt"],
        )
        if generated_prompt is None:
            st.warning("Gemini prompt generation is not available right now.")
        else:
            prompt_overrides[preview_pair_key] = generated_prompt
            prompt_sources[preview_pair_key] = "gemini"
            st.session_state[pending_prompt_key] = generated_prompt
            save_build_tab_state(
                selected_folder,
                ordered_names,
                st.session_state[selected_pairs_key],
                st.session_state[custom_order_key],
                st.session_state.get("build_pool_folder"),
                st.session_state[disabled_pairs_key],
                prompt_overrides,
                prompt_sources,
            )
            st.rerun()
    if prompt_action_cols[1].button(
        "Make more cinematic",
        use_container_width=True,
        key=f"build_generate_cinematic_prompt::{folder_key_text(selected_folder)}::{preview_pair_key}",
    ):
        generated_prompt = generate_build_pair_prompt_with_llm(
            preview_pair_key,
            preview_row["start"],
            preview_row["end"],
            source_lookup[preview_row["start"]],
            source_lookup[preview_row["end"]],
            preview_row["base_prompt"],
            normalized_prompt_text or preview_row["base_prompt"],
            imaginative=True,
        )
        if generated_prompt is None:
            st.warning("Gemini prompt generation is not available right now.")
        else:
            prompt_overrides[preview_pair_key] = generated_prompt
            prompt_sources[preview_pair_key] = "gemini_cinematic"
            st.session_state[pending_prompt_key] = generated_prompt
            save_build_tab_state(
                selected_folder,
                ordered_names,
                st.session_state[selected_pairs_key],
                st.session_state[custom_order_key],
                st.session_state.get("build_pool_folder"),
                st.session_state[disabled_pairs_key],
                prompt_overrides,
                prompt_sources,
            )
            st.rerun()
    if prompt_action_cols[2].button(
        "Ask Codex",
        use_container_width=True,
        key=f"build_prepare_codex::{folder_key_text(selected_folder)}::{preview_pair_key}",
    ):
        st.session_state[helper_mode_key] = "codex"
        st.session_state[f"build_pending_scroll_anchor::{folder_key_text(selected_folder)}"] = "build-prompt-helper-anchor"
        st.rerun()
    if prompt_action_cols[3].button(
        "Reset to default",
        use_container_width=True,
        key=f"build_reset_prompt::{folder_key_text(selected_folder)}::{preview_pair_key}",
    ):
        prompt_overrides.pop(preview_pair_key, None)
        prompt_sources.pop(preview_pair_key, None)
        st.session_state[pending_prompt_key] = preview_row["base_prompt"]
        st.session_state[helper_mode_key] = ""
        save_build_tab_state(
            selected_folder,
            ordered_names,
            st.session_state[selected_pairs_key],
            st.session_state[custom_order_key],
            st.session_state.get("build_pool_folder"),
            st.session_state[disabled_pairs_key],
            prompt_overrides,
            prompt_sources,
        )
        st.rerun()
    prompt_action_cols[4].markdown(
        f"<div class='extend-summary-card'><span>Used by Kling</span><strong>{'Custom prompt' if preview_pair_key in prompt_overrides else 'Default prompt'}</strong></div>",
        unsafe_allow_html=True,
    )
    save_build_tab_state(
        selected_folder,
        ordered_names,
        st.session_state[selected_pairs_key],
        st.session_state[custom_order_key],
        st.session_state.get("build_pool_folder"),
        st.session_state[disabled_pairs_key],
        prompt_overrides,
        prompt_sources,
    )

    videos_dir = os.path.join(selected_folder, "videos")
    status_path = os.path.join(videos_dir, "status.json")
    selected_existing_pair_keys = [
        pair_key
        for pair_key in st.session_state[selected_pairs_key]
        if pair_key in existing_pair_keys
    ]
    selected_missing_pair_keys = [
        pair_key
        for pair_key in st.session_state[selected_pairs_key]
        if pair_key in missing_pair_keys
    ]
    action_cols = st.columns([1.1, 1.25, 1.2], gap="small")
    use_credits_key = f"build_use_kling::{folder_key_text(selected_folder)}"
    if use_credits_key not in st.session_state:
        st.session_state[use_credits_key] = False
    if st.session_state[selected_pairs_key]:
        if selected_existing_pair_keys and not selected_missing_pair_keys:
            generation_caption = (
                f"{len(selected_existing_pair_keys)} selected pair(s) already have saved clips. "
                "Starting Kling again will rerun them and replace those segment files."
            )
        elif selected_existing_pair_keys and selected_missing_pair_keys:
            generation_caption = (
                f"{len(selected_missing_pair_keys)} selected pair(s) are missing and "
                f"{len(selected_existing_pair_keys)} already exist. Starting Kling will generate the missing clips and rerun the existing ones."
            )
        else:
            generation_caption = (
                f"Generate clips for {len(st.session_state[selected_pairs_key])} selected pair(s). "
                "The run starts in the background, and progress is tracked from the status file."
            )
    else:
        generation_caption = "Choose at least one pair to generate."
    st.caption(generation_caption)
    with action_cols[0]:
        st.markdown("**Kling run**")
        st.checkbox("Confirm credit use", key=use_credits_key)
    if st.session_state[selected_pairs_key]:
        if selected_existing_pair_keys and not selected_missing_pair_keys:
            generate_button_label = "Regenerate clips"
        elif selected_existing_pair_keys:
            generate_button_label = "Generate / rerun clips"
        elif len(st.session_state[selected_pairs_key]) == 1:
            generate_button_label = "Generate clip"
        else:
            generate_button_label = "Generate clips"
    else:
        generate_button_label = "Generate clips"
    generate_button_enabled = bool(st.session_state[selected_pairs_key]) and bool(st.session_state[use_credits_key])
    if action_cols[1].button(generate_button_label, use_container_width=True, type="primary", disabled=not generate_button_enabled):
        if not st.session_state[selected_pairs_key]:
            st.warning("Choose at least one pair to generate.")
        elif not st.session_state[use_credits_key]:
            st.warning("Tick `Confirm Kling credit use` before starting Kling generation.")
        else:
            generation_prompt_map = {
                row["pair_key"]: row["prompt"]
                for row in pair_rows
            }
            job_payload = {
                "started_at": time.time(),
                "source_folder": str(selected_folder),
                "ordered_names": ordered_names,
                "selected_pair_keys": st.session_state[selected_pairs_key],
                "video_dir": videos_dir,
                "status_path": status_path,
                "prompt_overrides": generation_prompt_map,
            }
            save_build_job_state(selected_folder, job_payload)
            start_build_generation_job(selected_folder, job_payload)
            st.session_state[f"build_generation_results::{folder_key_text(selected_folder)}"] = None
            st.session_state["build_generation_notice"] = (
                f"Started Kling generation for {len(st.session_state[selected_pairs_key])} pair(s). "
                "Watch the progress card below."
            )
            st.rerun()
    if not st.session_state[use_credits_key]:
        st.caption("Turn on `Confirm credit use` to enable Kling generation for this selection.")
    if action_cols[2].button(
        "Stitch movie",
        use_container_width=True,
        disabled=not existing_segments,
    ):
        try:
            stitch_result = stitch_pair_keys(
                [row["pair_key"] for row in pair_rows],
                videos_dir=videos_dir,
                output_file=os.path.join(videos_dir, "full_movie.mp4"),
            )
            st.success(f"Stitched {len(stitch_result['segments'])} segments into {relative_folder_label(Path(stitch_result['output_file']))}.")
        except Exception as exc:
            st.error(f"Stitch failed: {exc}")

    with st.expander("Optional: create a new prompt with Codex or another LLM", expanded=helper_mode == "codex"):
        if helper_mode == "codex":
            st.markdown("<div id='build-prompt-helper-anchor'></div>", unsafe_allow_html=True)
            render_extend_scroll_restore("build-prompt-helper-anchor")
        if helper_mode == "codex":
            st.caption("This helper does not change Kling directly. Paste the result back into the main prompt box if you want to use it.")
            st.info("Paste this request here in Codex with the two still images if you want me to write the exact Kling prompt.")
            st.text_area(
                "Ask Codex with this request",
                value=build_pair_prompt_codex_request(
                    preview_pair_key,
                    preview_row["start"],
                    preview_row["end"],
                    source_lookup[preview_row["start"]],
                    source_lookup[preview_row["end"]],
                    preview_row["base_prompt"],
                    normalized_prompt_text or preview_row["base_prompt"],
                ),
                height=260,
                key=f"build_prompt_codex_brief::{folder_key_text(selected_folder)}::{preview_pair_key}",
            )
            with st.expander("Use another LLM instead", expanded=False):
                st.text_area(
                    "Copy this helper brief",
                    value=build_pair_prompt_brief(
                        preview_pair_key,
                        preview_row["start"],
                        preview_row["end"],
                        preview_row["base_prompt"],
                        normalized_prompt_text or preview_row["base_prompt"],
                    ),
                    height=180,
                    key=f"build_prompt_brief::{folder_key_text(selected_folder)}::{preview_pair_key}",
                )
        else:
            st.caption("This helper does not change Kling directly. Paste the result back into the main prompt box if you want to use it.")
            st.text_area(
                "Copy this helper brief for another LLM",
                value=build_pair_prompt_brief(
                    preview_pair_key,
                    preview_row["start"],
                    preview_row["end"],
                    preview_row["base_prompt"],
                    normalized_prompt_text or preview_row["base_prompt"],
                ),
                height=180,
                key=f"build_prompt_brief::{folder_key_text(selected_folder)}::{preview_pair_key}",
            )

    build_job = load_build_job_state(selected_folder)
    if build_job:
        latest_run_pair_keys = [
            str(item)
            for item in build_job.get("selected_pair_keys", [])
            if isinstance(item, str)
        ]
        if latest_run_pair_keys != list(st.session_state[selected_pairs_key]):
            st.caption("The progress block below shows the latest started build run for this folder. Your current pair selection is different.")
        render_build_generation_progress(selected_folder, build_job, status_path)

    generation_notice = st.session_state.pop("build_generation_notice", "")
    if generation_notice:
        st.success(generation_notice)

    generation_results = st.session_state.get(f"build_generation_results::{folder_key_text(selected_folder)}")
    if generation_results:
        st.markdown("**Last generation run**")
        st.dataframe(generation_results, use_container_width=True, hide_index=True, height=260)


def render_generate_tab() -> None:
    st.subheader("Generate Videos")
    st.caption("Create AI video transitions between your sequenced images using Kling. Monitor progress and manage generation runs.")

    saved_state = load_build_tab_state()
    source_folder_text = str(saved_state.get("source_folder", ""))
    if not source_folder_text:
        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-icon">&#127916;</div>
                <h3>No sequence configured</h3>
                <p>Go to Build Sequence first to arrange your images and set up the pairs for video generation.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    source_folder = path_from_saved_text(source_folder_text)
    ordered_names = saved_state.get("ordered_images", [])
    if not ordered_names or len(ordered_names) < 2:
        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-icon">&#127916;</div>
                <h3>Need at least 2 images</h3>
                <p>Go to Build Sequence and arrange at least 2 images to create video transitions between them.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    disabled_pair_keys = set(saved_state.get("disabled_pair_keys", []))
    sequence_pairs = active_sequence_pairs(ordered_names, disabled_pair_keys)
    videos_dir = os.path.join(source_folder, "videos")
    status_path = os.path.join(videos_dir, "status.json")

    try:
        status_data = json.loads(Path(status_path).read_text(encoding="utf-8")) if Path(status_path).exists() else {}
    except (OSError, json.JSONDecodeError):
        status_data = {}

    existing_segments = set(ordered_segment_files_for_pair_keys(
        [pair_key for _, _, pair_key in sequence_pairs],
        videos_dir,
    ))

    total_pairs = len(sequence_pairs)
    done_count = 0
    failed_count = 0
    generating_count = 0
    pending_count = 0

    segment_cards_html = []
    for start_name, end_name, pair_key in sequence_pairs:
        pair_status = status_data.get(pair_key, {})
        seg_file = f"seg_{pair_key}.mp4"
        if isinstance(pair_status, dict) and pair_status.get("result") == "ok":
            status_label = "Done"
            status_class = "segment-card--done"
            done_count += 1
        elif isinstance(pair_status, dict) and pair_status.get("result") in {"submit_fail", "poll_fail"}:
            status_label = "Failed"
            status_class = "segment-card--failed"
            failed_count += 1
        elif seg_file in existing_segments:
            status_label = "Done"
            status_class = "segment-card--done"
            done_count += 1
        elif isinstance(pair_status, dict) and pair_status.get("task_id"):
            status_label = "Generating..."
            status_class = "segment-card--generating"
            generating_count += 1
        else:
            status_label = "Pending"
            status_class = ""
            pending_count += 1

        segment_cards_html.append(
            f'<div class="segment-card {status_class}">'
            f'<div class="seg-name">{pair_key}</div>'
            f'<div class="seg-status">{status_label}</div>'
            f'</div>'
        )

    summary_cols = st.columns(5, gap="small")
    summary_cols[0].markdown(
        f"<div class='extend-summary-card'><span>Total pairs</span><strong>{total_pairs}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[1].markdown(
        f"<div class='extend-summary-card'><span>Done</span><strong>{done_count}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[2].markdown(
        f"<div class='extend-summary-card'><span>Generating</span><strong>{generating_count}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[3].markdown(
        f"<div class='extend-summary-card'><span>Pending</span><strong>{pending_count}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[4].markdown(
        f"<div class='extend-summary-card'><span>Failed</span><strong>{failed_count}</strong></div>",
        unsafe_allow_html=True,
    )

    progress_value = done_count / total_pairs if total_pairs > 0 else 0
    st.progress(progress_value, text=f"{done_count} of {total_pairs} video clips generated")

    if done_count == total_pairs and total_pairs > 0:
        st.markdown(
            """
            <div class="success-banner">
                <div class="success-icon">&#127916;</div>
                <div>
                    <div class="success-text">All video clips generated</div>
                    <div class="success-detail">Move to Review & Fix to watch each clip and approve or redo any that need work.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_next_action_card(
        "Generation controls",
        "Start a Kling generation run, or go back to Build Sequence to adjust pairs and prompts before generating.",
    )

    control_cols = st.columns([1.2, 1, 1, 1], gap="small")
    use_credits_key = "generate_tab_use_kling"
    if use_credits_key not in st.session_state:
        st.session_state[use_credits_key] = False
    with control_cols[0]:
        st.checkbox("Confirm credit use", key=use_credits_key)

    selected_pair_keys = saved_state.get("selected_pair_keys", [pair_key for _, _, pair_key in sequence_pairs])
    prompt_overrides = saved_state.get("prompt_overrides", {})
    all_pair_keys = [pair_key for _, _, pair_key in sequence_pairs]
    folder_prompt_label = relative_folder_label(source_folder)
    generation_prompt_map = {}
    for pair_key in all_pair_keys:
        override = prompt_overrides.get(pair_key, "")
        base = get_pair_prompt(pair_key, folder_prompt_label)
        generation_prompt_map[pair_key] = override or base

    generate_enabled = bool(st.session_state[use_credits_key]) and pending_count > 0
    if control_cols[1].button(
        "Generate all pending",
        use_container_width=True,
        type="primary",
        disabled=not generate_enabled,
        key="generate_tab_start",
    ):
        missing_keys = [
            pair_key for _, _, pair_key in sequence_pairs
            if f"seg_{pair_key}.mp4" not in existing_segments
        ]
        job_payload = {
            "started_at": time.time(),
            "source_folder": str(source_folder),
            "ordered_names": ordered_names,
            "selected_pair_keys": missing_keys,
            "video_dir": videos_dir,
            "status_path": status_path,
            "prompt_overrides": generation_prompt_map,
        }
        save_build_job_state(source_folder, job_payload)
        start_build_generation_job(source_folder, job_payload)
        st.success(f"Started Kling generation for {len(missing_keys)} pending pair(s). Use Refresh to monitor progress.")
        st.rerun()

    if control_cols[2].button("Refresh", use_container_width=True, key="generate_tab_refresh"):
        st.rerun()

    if control_cols[3].button("Open videos folder", use_container_width=True, key="generate_tab_open_videos"):
        Path(videos_dir).mkdir(parents=True, exist_ok=True)
        open_folder_in_windows(Path(videos_dir))

    build_job = load_build_job_state(source_folder)
    if build_job:
        render_build_generation_progress(source_folder, build_job, status_path)

    st.markdown("**Segment status**")
    if segment_cards_html:
        st.markdown(
            '<div class="segment-grid">' + "".join(segment_cards_html) + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("No pairs configured. Go back to Build Sequence to set up your storyboard.")


def render_export_tab(run_id: str) -> None:
    st.subheader("Export Movie")
    st.caption("Combine all approved video clips into your final movie file.")

    saved_state = load_build_tab_state()
    source_folder_text = str(saved_state.get("source_folder", ""))
    if not source_folder_text:
        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-icon">&#127916;</div>
                <h3>No project configured</h3>
                <p>Set up your sequence in Build Sequence and generate video clips before exporting.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    source_folder = path_from_saved_text(source_folder_text)
    ordered_names = saved_state.get("ordered_images", [])
    disabled_pair_keys = set(saved_state.get("disabled_pair_keys", []))
    sequence_pairs = active_sequence_pairs(ordered_names, disabled_pair_keys)
    pair_keys = [pair_key for _, _, pair_key in sequence_pairs]
    videos_dir = os.path.join(source_folder, "videos")

    existing_segments = set(ordered_segment_files_for_pair_keys(pair_keys, videos_dir))
    total_pairs = len(pair_keys)
    ready_count = sum(1 for pair_key in pair_keys if f"seg_{pair_key}.mp4" in existing_segments)

    pairs = discover_clip_pairs()
    reviews = load_reviews(run_id)
    winners = load_winners(run_id)
    review_lookup = {(item.pair_id, item.version): item for item in reviews}
    queued_redo_lookup: dict[tuple[str, int], object] = {}
    pair_rows = build_pair_rows(pairs, review_lookup, queued_redo_lookup, winners) if pairs else []
    approved_count = sum(1 for row in pair_rows if row["status"] == "Approved")
    total_reviewed = len(pair_rows)

    summary_cols = st.columns(4, gap="small")
    summary_cols[0].markdown(
        f"<div class='extend-summary-card'><span>Total pairs</span><strong>{total_pairs}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[1].markdown(
        f"<div class='extend-summary-card'><span>Clips ready</span><strong>{ready_count}</strong></div>",
        unsafe_allow_html=True,
    )
    summary_cols[2].markdown(
        f"<div class='extend-summary-card'><span>Approved</span><strong>{approved_count}</strong></div>",
        unsafe_allow_html=True,
    )
    export_ready = ready_count > 0
    status_text = "Ready to export" if export_ready else "No clips available"
    summary_cols[3].markdown(
        f"<div class='extend-summary-card'><span>Status</span><strong>{status_text}</strong></div>",
        unsafe_allow_html=True,
    )

    if ready_count > 0:
        progress_value = ready_count / total_pairs if total_pairs > 0 else 0
        st.progress(progress_value, text=f"{ready_count} of {total_pairs} clips available for export")

    output_path = os.path.join(videos_dir, "full_movie.mp4")
    movie_exists = os.path.exists(output_path)

    if movie_exists:
        st.markdown(
            f"""
            <div class="success-banner">
                <div class="success-icon">&#127910;</div>
                <div>
                    <div class="success-text">Movie file ready</div>
                    <div class="success-detail">{relative_folder_label(Path(output_path))}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.video(output_path)

    render_next_action_card(
        "Export",
        f"Combine {ready_count} video clip(s) into one continuous movie file. "
        + ("This will replace the existing movie file." if movie_exists else "The movie will be saved in the videos folder."),
    )

    export_cols = st.columns([1.2, 1, 1], gap="small")
    if export_cols[0].button(
        "Build Final Movie",
        use_container_width=True,
        type="primary",
        disabled=not export_ready,
        key="export_build_movie",
    ):
        with st.spinner("Stitching video segments..."):
            try:
                stitch_result = stitch_pair_keys(
                    pair_keys,
                    videos_dir=videos_dir,
                    output_file=output_path,
                )
                st.success(
                    f"Stitched {len(stitch_result['segments'])} segments into "
                    f"{relative_folder_label(Path(stitch_result['output_file']))}."
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Stitch failed: {exc}")

    if export_cols[1].button("Open videos folder", use_container_width=True, key="export_open_videos"):
        Path(videos_dir).mkdir(parents=True, exist_ok=True)
        open_folder_in_windows(Path(videos_dir))

    if export_cols[2].button("Refresh", use_container_width=True, key="export_refresh"):
        st.rerun()

    if not export_ready:
        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-icon">&#128249;</div>
                <h3>No clips to export yet</h3>
                <p>Generate video clips in the Generate Videos step, then review them before exporting your final movie.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_review_and_fix_tab(run_id: str, status_filter: str) -> None:
    st.subheader("Review & Fix")
    st.caption("Watch each generated video clip. Approve the ones that look good, flag issues on the rest, and queue weak clips for regeneration.")

    pairs = discover_clip_pairs()
    if not pairs:
        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-icon">&#127909;</div>
                <h3>No video clips to review</h3>
                <p>Generate video clips first in the Generate Videos step, then come back here to review them.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    reviews = load_reviews(run_id)
    redo_requests = load_redo_queue(run_id)
    winners = load_winners(run_id)

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

    total_clips = len(pair_rows)
    approved_count = sum(1 for row in pair_rows if row["status"] == "Approved")
    unreviewed_count = sum(1 for row in pair_rows if row["status"] == "Needs review")
    redo_count = sum(1 for row in pair_rows if row["status"] == "Redo queued")

    summary_html = (
        f'<div class="progress-summary">'
        f'<div class="progress-item"><span>Total</span><strong>{total_clips}</strong></div>'
        f'<div class="progress-item"><span>Approved</span><strong>{approved_count}</strong></div>'
        f'<div class="progress-item"><span>Unreviewed</span><strong>{unreviewed_count}</strong></div>'
        f'<div class="progress-item"><span>Needs redo</span><strong>{redo_count}</strong></div>'
        f'</div>'
    )
    st.markdown(summary_html, unsafe_allow_html=True)

    if approved_count == total_clips:
        st.markdown(
            """
            <div class="success-banner">
                <div class="success-icon">&#127881;</div>
                <div>
                    <div class="success-text">All clips approved!</div>
                    <div class="success-detail">Your movie is ready. Move to Export Movie to create the final video.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    progress_value = approved_count / total_clips if total_clips > 0 else 0
    st.progress(progress_value, text=f"{approved_count} of {total_clips} clips approved")

    selected_pair = select_pair(pairs, pair_rows, status_filter)
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

    queued_items = [item for item in redo_requests if item.status == "queued"]
    if queued_items:
        with st.expander(f"Fix Queue ({len(queued_items)} queued)", expanded=False):
            render_redo_queue(redo_requests, review_lookup, winners, run_id)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');
        .stApp {
            font-family: 'Space Grotesk', sans-serif;
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
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
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
        /* --- Step indicator strip --- */
        .workflow-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin: 0.35rem 0 0.95rem;
            align-items: center;
        }
        .workflow-step {
            background: rgba(255, 248, 239, 0.84);
            border: 1px solid rgba(194, 120, 67, 0.16);
            border-radius: 999px;
            color: #8b5e3c;
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.82rem;
            font-weight: 600;
            padding: 0.38rem 0.75rem;
            transition: all 0.15s ease-out;
        }
        .workflow-step--active {
            background: linear-gradient(180deg, #fff1df 0%, #ffe2c2 100%);
            border-color: rgba(194, 120, 67, 0.35);
            color: #9a3412;
            box-shadow: 0 4px 12px rgba(194, 120, 67, 0.18);
        }
        .workflow-step .step-number {
            background: rgba(139, 94, 60, 0.14);
            border-radius: 50%;
            color: #8b5e3c;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 0.72rem;
            font-weight: 700;
            height: 22px;
            width: 22px;
            flex-shrink: 0;
        }
        .workflow-step--active .step-number {
            background: linear-gradient(180deg, #c85a2b 0%, #9a3412 100%);
            color: #fff;
        }
        .workflow-connector {
            color: #d4a574;
            font-size: 0.7rem;
            margin: 0 0.1rem;
        }
        /* --- Action cards --- */
        .next-action-card {
            background: linear-gradient(180deg, rgba(255, 245, 232, 0.96) 0%, rgba(255, 237, 213, 0.88) 100%);
            border: 1px solid rgba(194, 120, 67, 0.20);
            border-radius: 14px;
            box-shadow: 0 10px 22px rgba(120, 53, 15, 0.07);
            margin: 0.5rem 0 0.9rem;
            padding: 0.7rem 0.9rem;
        }
        .next-action-card span {
            color: #8b5e3c;
            display: block;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            margin-bottom: 0.2rem;
            text-transform: uppercase;
        }
        .next-action-card strong {
            color: #3f2415;
            display: block;
            font-size: 0.95rem;
            line-height: 1.35;
        }
        /* --- Empty state card --- */
        .empty-state-card {
            background: linear-gradient(180deg, rgba(255, 252, 248, 0.95) 0%, rgba(255, 245, 232, 0.90) 100%);
            border: 2px dashed rgba(194, 120, 67, 0.25);
            border-radius: 18px;
            padding: 2.5rem 2rem;
            text-align: center;
            margin: 1rem 0;
        }
        .empty-state-card .empty-icon {
            font-size: 2.5rem;
            margin-bottom: 0.8rem;
            opacity: 0.6;
        }
        .empty-state-card h3 {
            color: #7c2d12;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 1.2rem;
            margin: 0 0 0.4rem;
        }
        .empty-state-card p {
            color: #8b5e3c;
            font-size: 0.92rem;
            margin: 0;
            max-width: 32rem;
            margin-left: auto;
            margin-right: auto;
        }
        /* --- Phase header --- */
        .phase-header {
            background: linear-gradient(180deg, rgba(255, 248, 239, 0.96) 0%, rgba(255, 245, 232, 0.92) 100%);
            border: 1px solid rgba(194, 120, 67, 0.16);
            border-radius: 14px;
            display: flex;
            align-items: center;
            gap: 0.7rem;
            padding: 0.65rem 0.9rem;
            margin: 0.8rem 0 0.6rem;
        }
        .phase-header .phase-badge {
            background: linear-gradient(180deg, #c85a2b 0%, #9a3412 100%);
            border-radius: 10px;
            color: #fff;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            padding: 0.3rem 0.6rem;
            text-transform: uppercase;
            white-space: nowrap;
        }
        .phase-header .phase-title {
            color: #3f2415;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1rem;
            font-weight: 600;
        }
        .phase-header .phase-status {
            color: #8b5e3c;
            font-size: 0.82rem;
            margin-left: auto;
        }
        /* --- Progress summary bar --- */
        .progress-summary {
            background: rgba(255, 250, 245, 0.92);
            border: 1px solid rgba(194, 120, 67, 0.16);
            border-radius: 14px;
            display: flex;
            align-items: center;
            gap: 1.5rem;
            padding: 0.7rem 1rem;
            margin: 0.5rem 0 0.8rem;
        }
        .progress-summary .progress-item {
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
        }
        .progress-summary .progress-item span {
            color: #8b5e3c;
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.02em;
        }
        .progress-summary .progress-item strong {
            color: #3f2415;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.1rem;
            font-weight: 700;
        }
        /* --- Success banner --- */
        .success-banner {
            background: linear-gradient(180deg, #ecfdf5 0%, #d1fae5 100%);
            border: 1px solid #6ee7b7;
            border-radius: 14px;
            padding: 0.8rem 1rem;
            margin: 0.6rem 0;
            display: flex;
            align-items: center;
            gap: 0.7rem;
        }
        .success-banner .success-icon {
            font-size: 1.5rem;
        }
        .success-banner .success-text {
            color: #065f46;
            font-weight: 600;
            font-size: 0.95rem;
        }
        .success-banner .success-detail {
            color: #047857;
            font-size: 0.85rem;
        }
        /* --- Segment status grid --- */
        .segment-grid {
            display: grid;
            gap: 0.5rem;
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            margin: 0.6rem 0;
        }
        .segment-card {
            background: rgba(255, 250, 245, 0.92);
            border: 1px solid rgba(194, 120, 67, 0.14);
            border-radius: 12px;
            padding: 0.55rem 0.7rem;
            font-size: 0.82rem;
        }
        .segment-card--done {
            border-color: #6ee7b7;
            background: rgba(236, 253, 245, 0.6);
        }
        .segment-card--generating {
            border-color: #fbbf24;
            background: rgba(255, 251, 235, 0.6);
            animation: pulse-border 2s ease-in-out infinite;
        }
        .segment-card--failed {
            border-color: #fca5a5;
            background: rgba(254, 242, 242, 0.6);
        }
        .segment-card .seg-name {
            font-weight: 600;
            color: #3f2415;
            margin-bottom: 0.2rem;
        }
        .segment-card .seg-status {
            font-size: 0.75rem;
            font-weight: 500;
        }
        @keyframes pulse-border {
            0%, 100% { border-color: #fbbf24; }
            50% { border-color: #f59e0b; box-shadow: 0 0 8px rgba(245, 158, 11, 0.2); }
        }
        /* --- Info cards --- */
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
            font-family: 'Space Grotesk', sans-serif;
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
        .extend-thumb-title {
            color: #7c2d12;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.82rem;
            font-weight: 700;
            line-height: 1.2;
            margin: 0 0 0.35rem;
            min-height: 2rem;
            overflow-wrap: anywhere;
        }
        /* --- Sidebar --- */
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
        /* --- Typography --- */
        h1, h2, h3 {
            font-family: 'Space Grotesk', sans-serif;
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
        /* --- Metrics --- */
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
        /* --- Buttons --- */
        [data-testid="stButton"] > button,
        [data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(180deg, #fffaf4 0%, #fff1df 100%);
            border: 1px solid #ddb791;
            border-radius: 14px;
            box-shadow: 0 10px 22px rgba(120, 53, 15, 0.10);
            color: #7c2d12;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 600;
            min-height: 46px;
            padding: 0.65rem 1rem;
            white-space: nowrap;
            transition: all 0.15s ease-out;
        }
        [data-testid="stButton"] > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            background: linear-gradient(180deg, #fff5e8 0%, #ffe8cf 100%);
            border-color: #d48a50;
            color: #9a3412;
            transform: translateY(-1px);
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
        /* --- Expanders / Forms --- */
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
        /* --- Review elements --- */
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
        /* --- Upload area --- */
        .upload-zone {
            background: linear-gradient(180deg, rgba(255, 252, 248, 0.92) 0%, rgba(255, 245, 232, 0.85) 100%);
            border: 2px dashed rgba(194, 120, 67, 0.30);
            border-radius: 18px;
            padding: 2rem 1.5rem;
            text-align: center;
            transition: all 0.2s ease-out;
        }
        .upload-zone:hover {
            border-color: rgba(194, 120, 67, 0.50);
            background: linear-gradient(180deg, rgba(255, 248, 239, 0.96) 0%, rgba(255, 237, 213, 0.90) 100%);
        }
        .upload-zone h4 {
            color: #7c2d12;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 600;
            margin: 0 0 0.4rem;
        }
        .upload-zone p {
            color: #8b5e3c;
            font-size: 0.88rem;
            margin: 0;
        }
        /* --- Image gallery grid --- */
        .gallery-grid {
            display: grid;
            gap: 0.6rem;
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            margin: 0.6rem 0;
        }
        .gallery-item {
            background: rgba(255, 250, 245, 0.88);
            border: 1px solid rgba(194, 120, 67, 0.14);
            border-radius: 12px;
            overflow: hidden;
            transition: all 0.15s ease-out;
        }
        .gallery-item:hover {
            border-color: rgba(194, 120, 67, 0.35);
            box-shadow: 0 6px 16px rgba(120, 53, 15, 0.10);
        }
        .gallery-item img {
            width: 100%;
            aspect-ratio: 4/3;
            object-fit: cover;
        }
        .gallery-item .gallery-caption {
            color: #3f2415;
            font-size: 0.75rem;
            font-weight: 500;
            padding: 0.3rem 0.5rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_controls() -> tuple[str, str, str]:
    pending_workflow_step = st.session_state.pop("pending_workflow_step", None)
    saved_ui_state = load_ui_state()
    saved_workflow_step = str(saved_ui_state.get("active_workflow_step", "upload"))
    # Map old step keys to new ones for users with saved state from the previous workflow
    step_migration = {"extend": "prepare", "build": "sequence", "redo": "review"}
    if saved_workflow_step in step_migration:
        saved_workflow_step = step_migration[saved_workflow_step]
    if "active_workflow_step" not in st.session_state and saved_workflow_step in WORKFLOW_LABELS:
        st.session_state["active_workflow_step"] = saved_workflow_step
    if pending_workflow_step in WORKFLOW_LABELS:
        st.session_state["active_workflow_step"] = pending_workflow_step
    st.sidebar.header("Workflow")
    step_keys = [item[0] for item in WORKFLOW_STEPS]
    current_step = st.session_state.get("active_workflow_step", "upload")
    if current_step not in step_keys:
        current_step = step_migration.get(current_step, "upload")
        st.session_state["active_workflow_step"] = current_step
    active_step = st.sidebar.radio(
        "Section",
        options=step_keys,
        index=step_keys.index(current_step),
        format_func=lambda item: WORKFLOW_LABELS[item],
        key="active_workflow_step",
        label_visibility="collapsed",
    )
    save_ui_state(active_step)

    run_id = DEFAULT_RUN_ID
    if active_step in {"review", "export"}:
        st.sidebar.header("Project")
        run_id = st.sidebar.text_input("Project ID", value=DEFAULT_RUN_ID, key="sidebar_run_id").strip() or DEFAULT_RUN_ID

    if active_step == "prepare":
        render_extend_sidebar_controls()
        status_filter = st.session_state.get("sidebar_status_filter", "Needs review")
    elif active_step == "sequence":
        render_build_sidebar_controls()
        status_filter = st.session_state.get("sidebar_status_filter", "Needs review")
    elif active_step == "review":
        st.sidebar.header("Quick view")
        status_filter = st.sidebar.radio(
            "Show",
            options=STATUS_FILTERS,
            index=STATUS_FILTERS.index(st.session_state.get("sidebar_status_filter", "Needs review"))
            if st.session_state.get("sidebar_status_filter", "Needs review") in STATUS_FILTERS
            else STATUS_FILTERS.index("Needs review"),
            format_func=lambda item: FILTER_LABELS[item],
            key="sidebar_status_filter",
            label_visibility="collapsed",
        )
        st.sidebar.caption("Watch each clip, approve the good ones, and flag issues on the rest.")
    else:
        status_filter = st.session_state.get("sidebar_status_filter", "Needs review")

    return run_id, status_filter, active_step


def render_sidebar_summary_cards(items: list[tuple[str, str]]) -> None:
    card_cols = st.sidebar.columns(len(items), gap="small")
    for column, (label, value) in zip(card_cols, items):
        column.markdown(
            f"<div class='extend-summary-card'><span>{label}</span><strong>{value}</strong></div>",
            unsafe_allow_html=True,
        )


def render_extend_sidebar_controls() -> None:
    saved_state = load_extend_tab_state()
    source_folder = path_from_saved_text(str(saved_state.get("source_folder", relative_folder_label(OUTPAINTED_DIR))))
    output_text = str(saved_state.get("output_folder", DEFAULT_EXTENSION_OUTPUT_DIR))
    output_folder = resolve_extension_output_dir(output_text) or ROOT_DIR / DEFAULT_EXTENSION_OUTPUT_DIR
    active_image = str(saved_state.get("active_image", "-")) or "-"

    st.sidebar.header("Extend board")
    render_sidebar_summary_cards(
        [
            ("Source", relative_folder_label(source_folder)),
            ("Output", relative_folder_label(output_folder)),
        ]
    )
    st.sidebar.markdown(
        f"<div class='extend-details-card'><div><span>Active image</span><strong>{active_image}</strong></div><div><span>Only missing</span><strong>{'Yes' if saved_state.get('only_missing', False) else 'No'}</strong></div></div>",
        unsafe_allow_html=True,
    )
    button_cols = st.sidebar.columns(2, gap="small")
    if button_cols[0].button("Open source", use_container_width=True, key="sidebar_open_extend_source"):
        open_folder_in_windows(source_folder)
    if button_cols[1].button("Open output", use_container_width=True, key="sidebar_open_extend_output"):
        open_folder_in_windows(output_folder)
    st.sidebar.caption("Pick the working folders, step through images, and compare the saved extension against the original.")


def render_build_sidebar_controls() -> None:
    saved_state = load_build_tab_state()
    source_folder = st.session_state.get("build_source_folder")
    if not isinstance(source_folder, Path):
        source_folder = path_from_saved_text(str(saved_state.get("source_folder", "kling_test")))
    ordered_state_key = f"build_ordered_images::{folder_key_text(source_folder)}"
    ordered_images = st.session_state.get(ordered_state_key)
    if not isinstance(ordered_images, list):
        ordered_images = [str(item) for item in saved_state.get("ordered_images", []) if isinstance(item, str)]
    else:
        ordered_images = [str(item) for item in ordered_images]
    active_key = f"build_current_image::{folder_key_text(source_folder)}"
    active_image = st.session_state.get(active_key) or (ordered_images[0] if ordered_images else "-")
    active_index = ordered_images.index(active_image) + 1 if active_image in ordered_images else 0
    custom_order_key = f"build_custom_order::{folder_key_text(source_folder)}"
    custom_order = bool(st.session_state.get(custom_order_key, saved_state.get("custom_order", False)))

    st.sidebar.header("Build board")
    render_sidebar_summary_cards(
        [
            ("Images", str(len(ordered_images))),
            ("Pairs", str(max(0, len(ordered_images) - 1))),
        ]
    )
    st.sidebar.markdown(
        f"<div class='extend-details-card'><div><span>Folder</span><strong>{relative_folder_label(source_folder)}</strong></div><div><span>Active still</span><strong>{active_image}</strong></div><div><span>Position</span><strong>{active_index} of {len(ordered_images) if ordered_images else 0}</strong></div><div><span>Order</span><strong>{'Custom' if custom_order else 'Natural'}</strong></div></div>",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("Open build folder", use_container_width=True, key="sidebar_open_build_source"):
        open_folder_in_windows(source_folder)
    st.sidebar.caption("Arrange the storyboard, then generate video clips from the current sequence.")


def render_redo_sidebar_controls(run_id: str) -> None:
    redo_requests = load_redo_queue(run_id)
    queued = len([item for item in redo_requests if item.status == "queued"])
    waiting = len([item for item in redo_requests if item.status == "waiting_review"])
    failed = len([item for item in redo_requests if item.status == "failed"])

    st.sidebar.header("Retry board")
    render_sidebar_summary_cards(
        [
            ("Queued", str(queued)),
            ("Ready", str(waiting)),
            ("Failed", str(failed)),
        ]
    )
    st.sidebar.caption("Preview retry prompts, generate the selected reruns, then review the new versions.")


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

    button_cols = st.sidebar.columns([1, 1, 1.45], gap="small")
    if button_cols[0].button("Back", use_container_width=True, disabled=current_index == 0):
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
    if button_cols[2].button(
        "Next unreviewed",
        use_container_width=True,
        disabled=next_review_pair is None,
    ) and next_review_pair is not None:
        set_selected_pair(next_review_pair)
        st.rerun()

    current_row = pair_row_lookup[st.session_state.selected_pair_id]
    st.sidebar.caption(
        f"Current: {st.session_state.selected_pair_id} • {display_status(current_row['status'])} • {version_summary(current_row)}"
    )

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

    metric_cols = st.columns(4, gap="small")
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
    render_next_action_card(
        "Next action",
        "Approve the current version if it works. Otherwise save a redo or discussion review and move on.",
    )

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

            st.caption("Use the primary button only when this version is approved. Save review keeps redo and discussion decisions without jumping away.")
            submit_cols = st.columns(2, gap="medium")
            save_only = submit_cols[0].form_submit_button("Save review", use_container_width=True)
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
    render_next_action_card(
        "Next action",
        "Preview the rewritten prompts first, then generate only the retries worth spending credits on.",
    )
    if not redo_requests:
        st.info("No clips are queued for redo.")
        return

    queued_requests = [item for item in redo_requests if item.status == "queued"]
    waiting_review_requests = [item for item in redo_requests if item.status == "waiting_review"]
    failed_requests = [item for item in redo_requests if item.status == "failed"]

    metric_cols = st.columns(3, gap="small")
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

    st.caption("Preview the rewritten prompts first, then run only the retries you want to spend credits on.")
    control_cols = st.columns(3, gap="small")
    if control_cols[0].button("Preview retry prompts", use_container_width=True):
        if not selected_queue_keys:
            st.warning("Select at least one queued retry to preview.")
        else:
            st.session_state.redo_preview = preview_redo_queue(run_id, set(selected_queue_keys))

    run_confirmed = control_cols[1].checkbox("Use Kling credits", value=False)
    if control_cols[2].button(
        "Generate selected retries",
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
    summary_cols = st.sidebar.columns(3)
    summary_cols[0].metric("Left", unreviewed)
    summary_cols[1].metric("Redo", redo)
    summary_cols[2].metric("Rebuilt", rebuilt)
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
    source_tag = re.sub(r"[^A-Za-z0-9]+", "_", source_path.parent.name).strip("_").lower()
    if source_tag:
        candidate = target_dir / f"{stem}__{source_tag}{suffix}"
        if not candidate.exists():
            return candidate

    index = 2
    while True:
        if source_tag:
            candidate = target_dir / f"{stem}__{source_tag}_{index}{suffix}"
        else:
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
