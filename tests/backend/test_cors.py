"""Step 6 (Phase 4): CORS allow-list for local Vite dev server.

Proves that /health + a preflight for POST /projects both return the
Access-Control-Allow-Origin header for the 127.0.0.1:5173 origin.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_health_includes_cors_allow_origin() -> None:
    with TestClient(app) as c:
        r = c.get("/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_preflight_projects_allows_vite_origin() -> None:
    with TestClient(app) as c:
        r = c.options(
            "/projects",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    # Starlette's CORSMiddleware returns 200 on preflight
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert "POST" in r.headers.get("access-control-allow-methods", "")
