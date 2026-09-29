"""FastAPI application factory, router registration, security headers and static dashboard serving."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .. import __version__
from ..core.errors import EvidenceIntegrityError, UnsafeInputError, VisionSentinelError
from ..core.workspace import Workspace
from .deps import get_state
from .routers import assets, attacklab, auth, drift, evidence, findings, governance, provenance, scans, system
from .runner import JobRunner
from .security import API_CSP
from .settings import Settings
from .state import AppState
from .static import DashboardFiles

log = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers.setdefault("Content-Security-Policy", API_CSP)
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "same-origin")
        return response


def create_app(
    settings: Settings | None = None,
    workspace: Workspace | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    ws = workspace or Workspace.default()
    app_state = AppState.create(settings, ws)
    runner = JobRunner(app_state)
    app_state.runner = runner

    app = FastAPI(
        title="VisionSentinel",
        description="Air-Gapped Computer Vision Integrity & Assurance Platform",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.vs = app_state

    app.add_middleware(SecurityHeadersMiddleware)

    # Mount API routers
    app.include_router(auth.router)
    app.include_router(system.router)
    app.include_router(scans.router)
    app.include_router(assets.router)
    app.include_router(findings.router)
    app.include_router(governance.router)
    app.include_router(provenance.router)
    app.include_router(drift.router)
    app.include_router(attacklab.router)
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
