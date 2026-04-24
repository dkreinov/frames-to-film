"""Phase 5 Sub-Plan 2 Step 4: resolve_fal_key precedence + error path."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.deps import resolve_fal_key


def test_header_wins(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "env-value")
    assert resolve_fal_key("header-value") == "header-value"


def test_env_fallback_when_no_header(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "env-value")
    assert resolve_fal_key(None) == "env-value"
    # Empty / whitespace-only header also falls through to env.
    assert resolve_fal_key("   ") == "env-value"


def test_raises_400_when_neither_set(monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        resolve_fal_key(None)
    assert exc.value.status_code == 400
    assert "fal.ai API key required" in exc.value.detail
    assert "FAL_KEY" in exc.value.detail
