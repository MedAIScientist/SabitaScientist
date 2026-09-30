"""FastAPI application factory for the PM API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ...config.settings import get_effective_config
from ..db import configure_db_path, create_schema
from .audit_middleware import AuditMiddleware
from .rate_limiter import RateLimitMiddleware
from .routes import (
    admissions,
    ai_tools,
    ai_usage,
    assists,
    attachments,
    audit,
    auth,
    auth_oidc,
    bibliography,
    bulk,
    compute,
    conferences,
    copilot,
    cvat,
    cvat_provision,
    dashboard,
    datasets,
    dependencies,
    drafting,
    experiments,
    export_routes,
    exports,
    grants,
    help,
    integrations,
    irb,
    labs,
    literature_review,
    mcp,
    memory_routes,
    middleware_routes,
    patents,
    peer_review,
    phases,
    pipelines,
    projects,
    publications,
    runs,
    sandboxes,
    search,
    settings_routes,
    supervision,
    task_history,
    tasks,
    templates,
    users,
    webknossos,
    wiki,
)

_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


def create_app(db_path: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    ``db_path`` becomes the database this process serves: it is bound process-wide
    (see ``configure_db_path``) so every route, the audit middleware and the runner
    resolve the same file the app was created with. Passing ``None`` leaves the
    path to ``EVOSCIENTIST_PM_DB`` / ``DATA_DIR``.
    """
    configure_db_path(db_path)
    create_schema(db_path)  # idempotent — safe to call on every startup
    cfg = get_effective_config()

    app = FastAPI(
        title="EvoScientist PM API",
        version="1.0.0",
        docs_url="/api/docs" if cfg.pm_docs_enabled else None,
        redoc_url=None,
    )
    cors_origins = (
        ["*"]
        if not cfg.pm_cors_origins or cfg.pm_cors_origins == "*"
        else [o.strip() for o in cfg.pm_cors_origins.split(",") if o.strip()]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials="*" not in cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, max_requests=200, window_seconds=60)
    app.add_middleware(AuditMiddleware)

    @app.get("/api/v1/health", tags=["health"], include_in_schema=False)
    def health():
        return {"status": "ok"}

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(auth_oidc.router, prefix="/api/v1", tags=["auth-oidc"])
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
    app.include_router(drafting.router, prefix="/api/v1", tags=["drafting"])
    app.include_router(audit.router, prefix="/api/v1", tags=["audit"])
    app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
    app.include_router(export_routes.router, prefix="/api/v1", tags=["export"])
    app.include_router(bibliography.router, prefix="/api/v1", tags=["bibliography"])
    app.include_router(literature_review.router, prefix="/api/v1", tags=["literature"])
    app.include_router(peer_review.router, prefix="/api/v1", tags=["peer-review"])
    app.include_router(compute.router, prefix="/api/v1", tags=["compute"])
    app.include_router(ai_tools.router, prefix="/api/v1", tags=["ai-tools"])
    app.include_router(ai_usage.router, prefix="/api/v1/ai", tags=["ai-usage"])
    app.include_router(pipelines.router, prefix="/api/v1", tags=["deid-pipelines"])
    app.include_router(sandboxes.router, prefix="/api/v1", tags=["sandboxes"])
    app.include_router(exports.router, prefix="/api/v1", tags=["exports"])
    app.include_router(bulk.router, prefix="/api/v1", tags=["bulk"])
    app.include_router(task_history.router, prefix="/api/v1", tags=["task-history"])
    app.include_router(cvat_provision.router, prefix="/api/v1", tags=["cvat"])
    app.include_router(cvat.router, prefix="/api/v1", tags=["cvat"])
    app.include_router(webknossos.router, prefix="/api/v1", tags=["webknossos"])
    app.include_router(patents.router, prefix="/api/v1", tags=["patents"])
    app.include_router(mcp.router, prefix="/api/v1", tags=["mcp"])
    app.include_router(
        memory_routes.router, prefix="/api/v1", tags=["memory"]
    )
    app.include_router(
        middleware_routes.router, prefix="/api/v1", tags=["middleware"]
    )
    app.include_router(
        settings_routes.router, prefix="/api/v1", tags=["settings"]
    )
    app.include_router(grants.router, prefix="/api/v1/grants", tags=["grants"])
    app.include_router(help.router, prefix="/api/v1", tags=["help"])
    app.include_router(copilot.router, prefix="/api/v1", tags=["copilot"])
    app.include_router(integrations.router, prefix="/api/v1", tags=["integrations"])
    app.include_router(conferences.router, prefix="/api/v1/conferences", tags=["conferences"])
    app.include_router(irb.router, prefix="/api/v1/irb", tags=["irb"])
    app.include_router(datasets.router, prefix="/api/v1/datasets", tags=["datasets"])
    app.include_router(wiki.router, prefix="/api/v1", tags=["wiki"])
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(
        publications.router, prefix="/api/v1/publications", tags=["publications"]
    )
    app.include_router(admissions.router, prefix="/api/v1", tags=["admissions"])
    app.include_router(
        supervision.router, prefix="/api/v1/supervision", tags=["supervision"]
    )

    # Serve React SPA — only if the dist folder exists (i.e., frontend has been built)
    if _FRONTEND_DIST.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
            name="assets",
        )

        @app.api_route("/{full_path:path}", methods=["GET"], include_in_schema=False)
        async def serve_spa(full_path: str):
            if full_path.startswith("api/"):
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=404, content={"detail": "Not found"})
            file_path = _FRONTEND_DIST / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(_FRONTEND_DIST / "index.html"))

    return app
