"""FastAPI application factory for the EvoScientist runner service."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.runs import router as runs_router


def create_runner_app() -> FastAPI:
    """Create and configure the runner FastAPI app."""
    app = FastAPI(
        title="EvoScientist Runner",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
    )

    # Only allow PM backend (localhost) — runner is not browser-accessible
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:7860", "http://localhost:7860"],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(runs_router)
    return app
