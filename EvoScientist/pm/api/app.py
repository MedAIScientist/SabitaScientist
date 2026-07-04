"""FastAPI application factory for the PM API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..db import create_schema
from .routes import (
    admissions,
    assists,
    attachments,
    auth,
    dependencies,
    experiments,
    labs,
    phases,
    projects,
    runs,
    tasks,
    templates,
    users,
)

_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


def create_app(db_path: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    create_schema(db_path)  # idempotent — safe to call on every startup

    app = FastAPI(
        title="EvoScientist PM API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health", tags=["health"], include_in_schema=False)
    def health():
        return {"status": "ok"}

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
    app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
    app.include_router(tasks.router, prefix="/api/v1/projects", tags=["tasks"])
    app.include_router(runs.router, prefix="/api/v1/projects", tags=["runs"])
    app.include_router(experiments.router, prefix="/api/v1/projects", tags=["experiments"])
    app.include_router(
        assists.router, prefix="/api/v1/projects", tags=["assists"]
    )
    app.include_router(
        assists.global_router, prefix="/api/v1", tags=["assists"]
    )
    app.include_router(phases.router, prefix="/api/v1/projects", tags=["phases"])
    app.include_router(dependencies.router, prefix="/api/v1/projects", tags=["dependencies"])
    app.include_router(
        attachments.router, prefix="/api/v1/projects", tags=["attachments"]
    )
    app.include_router(
        attachments.global_router, prefix="/api/v1", tags=["attachments"]
    )
    app.include_router(labs.router, prefix="/api/v1/labs", tags=["labs"])
    app.include_router(templates.router, prefix="/api/v1/templates", tags=["templates"])
    app.include_router(
        admissions.router, prefix="/api/v1", tags=["admissions"]
    )

    # Serve React SPA — only if the dist folder exists (i.e., frontend has been built)
    if _FRONTEND_DIST.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
            name="assets",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            return FileResponse(str(_FRONTEND_DIST / "index.html"))

    return app
