"""FastAPI application factory for the PM API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..db import create_schema
from .routes import auth, experiments, projects, runs, tasks, users

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
        allow_origins=["http://localhost:7860", "http://127.0.0.1:7860"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
    app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
    app.include_router(tasks.router, prefix="/api/v1/projects", tags=["tasks"])
    app.include_router(runs.router, prefix="/api/v1/projects", tags=["runs"])
    app.include_router(experiments.router, prefix="/api/v1/projects", tags=["experiments"])

    # Serve React SPA — only if the dist folder exists (i.e., frontend has been built)
    if _FRONTEND_DIST.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
            name="assets",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(_full_path: str):
            return FileResponse(str(_FRONTEND_DIST / "index.html"))

    return app
