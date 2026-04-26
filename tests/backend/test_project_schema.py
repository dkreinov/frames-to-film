from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.services.project_schema import (
    AUDIO_DIRNAME,
    CLIPS_DIRNAME,
    CLIPS_RAW_DIRNAME,
    EXTENDED_DIRNAME,
    INPUTS_DIRNAME,
    METADATA_DIRNAME,
    STORAGE_ROOT_DIRNAME,
    ProjectMeta,
    project_root,
)


def test_storage_root_is_projects():
    assert STORAGE_ROOT_DIRNAME == "projects"


def test_subfolder_constants():
    assert INPUTS_DIRNAME == "inputs"
    assert EXTENDED_DIRNAME == "extended"
    assert CLIPS_DIRNAME == "clips"
    assert CLIPS_RAW_DIRNAME == "raw"
    assert AUDIO_DIRNAME == "audio"
    assert METADATA_DIRNAME == "metadata"


def test_project_meta_minimal():
    meta = ProjectMeta(slug="olga", name="Olga", created_at=date(2026, 4, 26))
    assert meta.slug == "olga"
    assert meta.status == "draft"
    assert meta.tags == []


def test_project_meta_rejects_bad_slug():
    with pytest.raises(ValidationError):
        ProjectMeta(slug="Olga Movie!", name="x", created_at=date.today())


def test_project_root_local_user():
    root = Path("/tmp/projects")
    assert project_root(root, "local", "olga") == Path("/tmp/projects/olga")


def test_project_root_named_user():
    root = Path("/tmp/projects")
    assert project_root(root, "user-123", "olga") == Path("/tmp/projects/user-123/olga")
