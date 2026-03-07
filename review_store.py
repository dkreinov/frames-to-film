from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from review_models import ClipPair, ClipVersion, RedoRequest, ReviewPaths, ReviewRecord


ROOT_DIR = Path(__file__).resolve().parent
RUNS_DIR = ROOT_DIR / "pipeline_runs"
DEFAULT_RUN_ID = "local-review-run"
VIDEOS_DIR = ROOT_DIR / "kling_test" / "videos"
FRAMES_DIR = ROOT_DIR / "kling_test"
SEGMENT_RE = re.compile(r"^seg_(?P<pair>.+?)(?:_v(?P<version>\d+))?\.mp4$")


def get_review_paths(run_id: str = DEFAULT_RUN_ID) -> ReviewPaths:
    run_dir = RUNS_DIR / run_id
    return ReviewPaths(
        run_id=run_id,
        run_dir=run_dir,
        review_file=run_dir / "reviews.json",
        redo_queue_file=run_dir / "redo_queue.json",
    )


def ensure_review_files(run_id: str = DEFAULT_RUN_ID) -> ReviewPaths:
    paths = get_review_paths(run_id)
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    if not paths.review_file.exists():
        _write_json(paths.review_file, {"run_id": run_id, "reviews": []})
    if not paths.redo_queue_file.exists():
        _write_json(paths.redo_queue_file, {"run_id": run_id, "redo_requests": []})
    winners_file = _winners_file(paths.run_dir)
    if not winners_file.exists():
        _write_json(winners_file, {"run_id": run_id, "winners": {}})
    return paths


def discover_clip_pairs(videos_dir: Path = VIDEOS_DIR) -> list[ClipPair]:
    pair_map: dict[str, ClipPair] = {}

    for path in sorted(videos_dir.glob("seg_*.mp4")):
        parsed = parse_segment_filename(path.name)
        if parsed is None:
            continue

        pair_id, version = parsed
        start_frame_id, end_frame_id = split_pair_id(pair_id)
        pair = pair_map.get(pair_id)
        if pair is None:
            pair = ClipPair(
                pair_id=pair_id,
                start_frame_id=start_frame_id,
                end_frame_id=end_frame_id,
            )
            pair_map[pair_id] = pair

        pair.versions.append(
            ClipVersion(
                pair_id=pair_id,
                version=version,
                filename=path.name,
                video_path=str(path),
            )
        )

    for pair in pair_map.values():
        pair.versions.sort(key=lambda item: item.version)

    return sorted(pair_map.values(), key=lambda item: pair_sort_key(item.pair_id))


def parse_segment_filename(filename: str) -> tuple[str, int] | None:
    match = SEGMENT_RE.match(filename)
    if not match:
        return None
    pair_id = match.group("pair")
    version = int(match.group("version") or "1")
    return pair_id, version


def split_pair_id(pair_id: str) -> tuple[str, str]:
    start, sep, end = pair_id.partition("_to_")
    if not sep or not start or not end:
        raise ValueError(f"Invalid pair id: {pair_id}")
    return start, end


def pair_sort_key(pair_id: str) -> tuple[tuple[int, str], tuple[int, str]]:
    start, end = split_pair_id(pair_id)
    return frame_sort_key(start), frame_sort_key(end)


def frame_sort_key(frame_id: str) -> tuple[int, str]:
    match = re.match(r"^(?P<num>\d+)(?:_(?P<suffix>[a-z]))?$", frame_id)
    if not match:
        return 9999, frame_id
    return int(match.group("num")), match.group("suffix") or ""


def frame_image_path(frame_id: str, frames_dir: Path = FRAMES_DIR) -> Path:
    for ext in (".jpg", ".jpeg", ".png"):
        candidate = frames_dir / f"{frame_id}{ext}"
        if candidate.exists():
            return candidate
    return frames_dir / f"{frame_id}.jpg"


def load_reviews(run_id: str = DEFAULT_RUN_ID) -> list[ReviewRecord]:
    paths = ensure_review_files(run_id)
    payload = _read_json(paths.review_file)
    return [ReviewRecord(**item) for item in payload.get("reviews", [])]


def save_review(review: ReviewRecord, run_id: str = DEFAULT_RUN_ID) -> None:
    reviews = load_reviews(run_id)
    filtered = [
        item
        for item in reviews
        if not (item.pair_id == review.pair_id and item.version == review.version)
    ]
    filtered.append(review)
    paths = ensure_review_files(run_id)
    _write_json(
        paths.review_file,
        {
            "run_id": run_id,
            "reviews": [item.to_dict() for item in sorted(filtered, key=_review_sort_key)],
        },
    )


def load_redo_queue(run_id: str = DEFAULT_RUN_ID) -> list[RedoRequest]:
    paths = ensure_review_files(run_id)
    payload = _read_json(paths.redo_queue_file)
    return [RedoRequest(**item) for item in payload.get("redo_requests", [])]


def queue_redo(request: RedoRequest, run_id: str = DEFAULT_RUN_ID) -> None:
    redo_requests = load_redo_queue(run_id)
    filtered = [
        item
        for item in redo_requests
        if not (item.pair_id == request.pair_id and item.source_version == request.source_version)
    ]
    filtered.append(request)
    paths = ensure_review_files(run_id)
    _write_json(
        paths.redo_queue_file,
        {
            "run_id": run_id,
            "redo_requests": [item.to_dict() for item in filtered],
        },
    )


def remove_redo_request(pair_id: str, source_version: int, run_id: str = DEFAULT_RUN_ID) -> None:
    redo_requests = load_redo_queue(run_id)
    filtered = [
        item
        for item in redo_requests
        if not (item.pair_id == pair_id and item.source_version == source_version)
    ]
    paths = ensure_review_files(run_id)
    _write_json(
        paths.redo_queue_file,
        {
            "run_id": run_id,
            "redo_requests": [item.to_dict() for item in filtered],
        },
    )


def load_winners(run_id: str = DEFAULT_RUN_ID) -> dict[str, int]:
    paths = ensure_review_files(run_id)
    payload = _read_json(_winners_file(paths.run_dir))
    return {str(key): int(value) for key, value in payload.get("winners", {}).items()}


def save_winner(pair_id: str, version: int, run_id: str = DEFAULT_RUN_ID) -> None:
    winners = load_winners(run_id)
    winners[pair_id] = version
    paths = ensure_review_files(run_id)
    _write_json(
        _winners_file(paths.run_dir),
        {
            "run_id": run_id,
            "winners": winners,
        },
    )


def latest_clip_versions(pairs: Iterable[ClipPair]) -> dict[str, ClipVersion]:
    latest: dict[str, ClipVersion] = {}
    for pair in pairs:
        version = pair.latest_version()
        if version is not None:
            latest[pair.pair_id] = version
    return latest


def _review_sort_key(review: ReviewRecord) -> tuple[tuple[int, str], tuple[int, str], int]:
    return pair_sort_key(review.pair_id) + (review.version,)


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _winners_file(run_dir: Path) -> Path:
    return run_dir / "winners.json"
