"""FastAPI application factory, router registration, security headers and static dashboard serving."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .. import __version__
from ..core.airgap import EgressViolation
from ..core.errors import EvidenceIntegrityError, RunnerUnavailableError, UnsafeInputError, VisionSentinelError
from ..core.workspace import Workspace
from .routers import admin, assets, attacklab, auth, drift, evidence, findings, governance, jobs, provenance, scans, system
from .runner import JobRunner, recover_interrupted_work
from .security import BodyLimit, SecurityHeaders
from .settings import Settings
from .state import AppState
from .static import DashboardFiles

log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    workspace: Workspace | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    ws = workspace or Workspace.default()
    app_state = AppState.create(settings, ws)
    runner = JobRunner(app_state)
    app_state.runner = runner

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            recover_interrupted_work(app_state)
            yield
        finally:
            runner.shutdown()
            app_state.db.dispose()

    app = FastAPI(
        title="VisionX",
        description="Air-Gapped Computer Vision Integrity & Assurance Platform",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.vs = app_state

    # Starlette wraps middleware in reverse registration order: headers are outermost so
    # rejected host/body responses receive the same policy as ordinary responses.
    app.add_middleware(BodyLimit, default_limit=settings.max_json_bytes,
                       upload_limit=settings.max_upload_bytes,
                       upload_prefix=f"{assets.router.prefix}/upload")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(SecurityHeaders)

    # Mount API routers
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(system.router)
    app.include_router(scans.router)
    app.include_router(assets.router)
    app.include_router(findings.router)
    app.include_router(governance.router)
    app.include_router(provenance.router)
    app.include_router(drift.router)
    app.include_router(attacklab.router)
    app.include_router(jobs.router)
    app.include_router(evidence.router)

    # Exception Handlers
    @app.exception_handler(VisionSentinelError)
    async def vs_error_handler(request: Request, exc: VisionSentinelError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(exc), "hint": getattr(exc, "hint", None)},
        )

    @app.exception_handler(UnsafeInputError)
    async def unsafe_error_handler(request: Request, exc: UnsafeInputError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"unsafe input: {exc}", "hint": getattr(exc, "hint", None)},
        )

    @app.exception_handler(EvidenceIntegrityError)
    async def evidence_error_handler(request: Request, exc: EvidenceIntegrityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": f"evidence integrity check failed: {exc}"},
        )

    @app.exception_handler(RunnerUnavailableError)
    async def runner_unavailable_handler(request: Request, exc: RunnerUnavailableError):
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"error": str(exc)})

    @app.exception_handler(EgressViolation)
    async def egress_violation_handler(request: Request, exc: EgressViolation):
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={"error": "offline workload policy blocked external network access"})

    # Static Dashboard fallback if configured
    dash_dir = settings.dashboard_dir
    if not dash_dir:
        # Check standard locations
        candidates = [
            ws.root / "dashboard",
            Path(__file__).resolve().parents[3] / "frontend" / "out",
            Path(__file__).resolve().parents[3] / "frontend" / "dist",
        ]
        for c in candidates:
            if c.is_dir():
                dash_dir = c
                break

    if dash_dir and dash_dir.is_dir():
        dashboard_files = DashboardFiles(dash_dir)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_dashboard(full_path: str):
            return dashboard_files.response(full_path)

    return app
