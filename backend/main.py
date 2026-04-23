"""FastAPI entry point for the olga_movie backend.

Phase 2 scaffold — routers are added by subsequent steps.
Boot with: `uvicorn backend.main:app --reload`.
"""
from __future__ import annotations

from fastapi import FastAPI

from backend.routers import (
    artifacts,
    extend,
    generate,
    jobs,
    prepare,
    projects,
    prompts,
    review,
    stitch,
    uploads,
)

app = FastAPI(title="olga_movie backend", version="0.3.0")
app.include_router(projects.router)
app.include_router(uploads.router)
app.include_router(jobs.router)
app.include_router(prepare.router)
app.include_router(extend.router)
app.include_router(generate.router)
app.include_router(review.router)
app.include_router(stitch.router)
app.include_router(artifacts.router)
app.include_router(prompts.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
