"""Shared FastAPI dependencies — DB path, storage root, user id, API keys."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Header, HTTPException

from backend.db import DEFAULT_DB_PATH, REPO_ROOT
from backend.services.project_schema import STORAGE_ROOT_DIRNAME

DEFAULT_STORAGE_ROOT = REPO_ROOT / STORAGE_ROOT_DIRNAME


def get_db_path() -> Path:
    return DEFAULT_DB_PATH


def get_storage_root() -> Path:
    return DEFAULT_STORAGE_ROOT


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    return (x_user_id or "local").strip() or "local"


def resolve_gemini_key(x_gemini_key: str | None) -> str:
    """Resolve the Gemini API key for api-mode calls.

    Precedence:
    1. `X-Gemini-Key` header value (passed in from the handler).
    2. `gemini` env var (legacy `.env` path for local dev).

    Raises `HTTPException(400)` if neither is set. Handlers should call
    this only when the request actually needs a key (mode == "api");
    mock-mode flows should not reach this resolver.
    """
    key = (x_gemini_key or "").strip() or os.getenv("gemini")
    if not key:
        raise HTTPException(
            status_code=400,
            detail=(
                "Gemini API key required for api mode. "
                "Paste a key in Settings or set the 'gemini' env var."
            ),
        )
    return key


def resolve_fal_key(x_fal_key: str | None) -> str:
    """Resolve the fal.ai API key for api-mode video generation.

    Same precedence shape as `resolve_gemini_key`:
    1. `X-Fal-Key` header (pasted in Settings by the user).
    2. `FAL_KEY` env var (local dev fallback).
    """
    key = (x_fal_key or "").strip() or os.getenv("FAL_KEY")
    if not key:
        raise HTTPException(
            status_code=400,
            detail=(
                "fal.ai API key required for api mode. "
                "Paste a key in Settings or set the 'FAL_KEY' env var."
            ),
        )
    return key


def resolve_qwen_key(x_qwen_key: str | None) -> str:
    """Resolve the Qwen API key (Alibaba DashScope) for vision judges.

    Same precedence shape as other resolvers:
    1. `X-Qwen-Key` header.
    2. `QWEEN_KEY` env var (operator-chosen spelling 2026-04-25).

    Used by `prompt_judge` + `clip_judge` v2 (qwen3-vl-plus default).
    """
    key = (x_qwen_key or "").strip() or os.getenv("QWEEN_KEY")
    if not key:
        raise HTTPException(
            status_code=400,
            detail=(
                "Qwen API key required. Paste a key in Settings or set "
                "the 'QWEEN_KEY' env var (Alibaba DashScope, qwen.ai/apiplatform)."
            ),
        )
    return key


def resolve_deepseek_key(x_deepseek_key: str | None) -> str:
    """Resolve the DeepSeek API key for movie_judge calls (Phase 7.1+).

    Same precedence shape:
    1. `X-DeepSeek-Key` header.
    2. `DEEPSEEK_KEY` env var.

    Raises `HTTPException(400)` if neither is set. Judges fall back to
    neutral 3.0 scores when called without a key, so this resolver is
    only used by routes that explicitly require the judge to run.
    """
    key = (x_deepseek_key or "").strip() or os.getenv("DEEPSEEK_KEY")
    if not key:
        raise HTTPException(
            status_code=400,
            detail=(
                "DeepSeek API key required for movie_judge. "
                "Paste a key in Settings or set the 'DEEPSEEK_KEY' env var."
            ),
        )
    return key
