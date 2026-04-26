"""Canonical project storage schema constants and metadata model.

All consumers (services, routers, tests) MUST import from here rather
than hardcoding subfolder strings. Layout matches docs/PROJECT_SCHEMA.md.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

STORAGE_ROOT_DIRNAME = "projects"
ARCHIVE_DIRNAME = "_archive"
TEMPLATE_DIRNAME = "_template"

INPUTS_DIRNAME = "inputs"
EXTENDED_DIRNAME = "extended"
PROMPTS_DIRNAME = "prompts"
CLIPS_DIRNAME = "clips"
CLIPS_RAW_DIRNAME = "raw"
CLIPS_SELECTED_DIRNAME = "selected"
AUDIO_DIRNAME = "audio"
FINAL_DIRNAME = "final"
EXPORTS_DIRNAME = "exports"
METADATA_DIRNAME = "metadata"
LOGS_DIRNAME = "logs"

ProjectStatus = Literal["draft", "in_progress", "review", "delivered", "archived"]


class ProjectMeta(BaseModel):
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str
    created_at: date
    status: ProjectStatus = "draft"
    tags: list[str] = Field(default_factory=list)
    audio_track: str | None = None
    source: str = "operator_upload"


def project_root(storage_root: Path, user_id: str, slug: str) -> Path:
    """Return the canonical path to a project's folder.

    Operator-driven phase (`user_id == "local"`): `{storage_root}/{slug}/`.
    Multi-user phase: `{storage_root}/{user_id}/{slug}/`.
    """
    if user_id == "local":
        return storage_root / slug
    return storage_root / user_id / slug
