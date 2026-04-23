"""FastAPI entry point for the olga_movie backend.

Phase 2 scaffold — routers are added by subsequent steps.
Boot with: `uvicorn backend.main:app --reload`.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import (
    artifacts,
    extend,
    generate,
    jobs,
    order,
    outputs,
    prepare,
    projects,
    prompts,
    review,
    stitch,
    uploads,
)

app = FastAPI(title="olga_movie backend", version="0.4.0")

# Phase 4: allow local Vite dev server + localhost equivalents. Tighten in
# Phase 6 for production deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
app.include_router(outputs.router)
app.include_router(order.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
