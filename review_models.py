from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


ISSUE_TAGS = (
    "face_bad",
    "identity_drift",
    "hands_body_bad",
    "transition_bad",
    "scenario_wrong",
    "background_wrong",
    "style_mismatch",
    "too_fast",
    "too_slow",
    "artifacts",
    "emotion_wrong",
    "prompt_ignored",
)

DECISIONS = (
    "approve",
    "redo",
    "needs_discussion",
)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class ClipVersion:
    pair_id: str
    version: int
    filename: str
    video_path: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ClipPair:
    pair_id: str
    start_frame_id: str
    end_frame_id: str
    versions: list[ClipVersion] = field(default_factory=list)

    def latest_version(self) -> ClipVersion | None:
        if not self.versions:
            return None
        return max(self.versions, key=lambda item: item.version)

    def to_dict(self) -> dict:
        return {
            "pair_id": self.pair_id,
            "start_frame_id": self.start_frame_id,
            "end_frame_id": self.end_frame_id,
            "versions": [item.to_dict() for item in self.versions],
        }


@dataclass(slots=True)
class ReviewRecord:
    pair_id: str
    version: int
    decision: str
    rating: int | None = None
    issues: list[str] = field(default_factory=list)
    note: str = ""
    reviewed_by: str = "local-user"
    reviewed_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class RedoRequest:
    pair_id: str
    source_version: int
    issues: list[str] = field(default_factory=list)
    note: str = ""
    status: str = "queued"
    queued_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ReviewPaths:
    run_id: str
    run_dir: Path
    review_file: Path
    redo_queue_file: Path
