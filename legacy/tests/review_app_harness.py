from __future__ import annotations

import tempfile
from pathlib import Path

import review_app


TEMP_ROOT = Path(tempfile.gettempdir()) / "olga_movie_ui_harness"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)

review_app.EXTEND_TAB_STATE_PATH = TEMP_ROOT / "extend_tab_state.json"
review_app.BUILD_TAB_STATE_PATH = TEMP_ROOT / "build_movie_state.json"
review_app.BUILD_JOB_DIR = TEMP_ROOT / "build_jobs"
review_app.UI_STATE_PATH = TEMP_ROOT / "ui_state.json"


def _seed_state() -> None:
    source_folder = review_app.ROOT_DIR / "Olia_continue" / "extend_api"
    ordered_images = [path.name for path in review_app.discover_orderable_images(source_folder)[:5]]
    selected_pair_keys = [
        pair_key
        for _, _, pair_key in review_app.build_pairs_from_sequence(ordered_images)
    ]
    review_app.save_extend_tab_state(
        source_folder=review_app.ROOT_DIR / "Olia_continue",
        output_folder="Olia_continue\\extend_api",
        only_missing=False,
        active_image=ordered_images[0] if ordered_images else "",
        swap_compare_sides=False,
        local_judge_enabled=False,
    )
    review_app.save_build_tab_state(
        source_folder=source_folder,
        ordered_images=ordered_images,
        selected_pair_keys=selected_pair_keys,
        custom_order=True,
    )
    review_app.save_ui_state("extend")


def _fake_open_folder(_path: Path) -> None:
    return None


def _fake_browse_for_folder(initial_dir: Path) -> Path:
    return initial_dir


def _fake_generate_prompt(*_args, **_kwargs) -> str:
    return (
        "Gentle push-in. Transition naturally between the two stills. "
        "Preserve the same people, stable faces, and the same setting."
    )


def _fake_start_build_generation_job(source_folder: Path, job_payload: dict[str, object]) -> None:
    payload = dict(job_payload)
    payload["pid"] = 99999
    review_app.save_build_job_state(source_folder, payload)


def _fake_stop_build_generation_job(_job_state: dict[str, object]) -> bool:
    return True


review_app.open_folder_in_windows = _fake_open_folder
review_app.browse_for_folder = _fake_browse_for_folder
review_app.generate_build_pair_prompt_with_llm = _fake_generate_prompt
review_app.start_build_generation_job = _fake_start_build_generation_job
review_app.stop_build_generation_job = _fake_stop_build_generation_job

_seed_state()
review_app.main()
