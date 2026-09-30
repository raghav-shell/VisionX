"""FastAPI dependencies: application state, authenticated principal, role and CSRF enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status

from ..contracts import Role
from ..storage import Session, User
from .security import CSRF_HEADER, SESSION_COOKIE, csrf_ok, origin_ok, resolve_session
from .state import AppState

DIRECT_DEMO_USERNAME = "visionx-demo-analyst"
DIRECT_DEMO_DISPLAY_NAME = "VisionX local demo analyst"


def get_state(request: Request) -> AppState:
    return request.app.state.vs


@dataclass
class Principal:
    user: User
    session: Session

    @property
    def username(self) -> str:
        return self.user.username

    @property
    def role(self) -> Role:
        return Role(self.user.role)


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def is_loopback_client(request: Request) -> bool:
    try:
        return ip_address(client_key(request)).is_loopback
    except ValueError:
        return False


def direct_demo_principal() -> Principal:
    user = User(id=str(uuid4()), username=DIRECT_DEMO_USERNAME,
                display_name=DIRECT_DEMO_DISPLAY_NAME, role=Role.ANALYST.value,
                password_hash="", disabled=False)
    session = Session(token_hash="", user_id=user.id, csrf_token="",
                      expires_at=datetime.now(timezone.utc), client="loopback")
    return Principal(user, session)


def current_principal(request: Request, state: AppState = Depends(get_state)) -> Principal:
    found = resolve_session(state.db, request.cookies.get(SESSION_COOKIE))
    if found is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    return Principal(*found)


def viewer_or_demo(request: Request, state: AppState = Depends(get_state)) -> Principal | None:
    """Allow authenticated viewers or explicitly configured anonymous read-only access."""
    found = resolve_session(state.db, request.cookies.get(SESSION_COOKIE))
    if found is not None:
        return Principal(*found)
    if state.settings.direct_demo and is_loopback_client(request):
        return direct_demo_principal()
    if state.settings.anonymous_read_only:
        return None
    if state.settings.demo_mode and request.headers.get("X-VisionX-Demo") == "1":
        return None
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")


def _same_origin(request: Request, state: AppState) -> set[str]:
    host = request.headers.get("host", "")
    origins = {f"http://{host}", f"https://{host}", *state.settings.extra_origins}
    if state.settings.direct_demo:
        origin = request.headers.get("origin", "").rstrip("/")
        parsed = urlsplit(origin)
        hostname = parsed.hostname or ""
        try:
            loopback_origin = ip_address(hostname).is_loopback
        except ValueError:
            loopback_origin = hostname == "localhost"
        if parsed.scheme in {"http", "https"} and loopback_origin:
            origins.add(origin)
    return origins


def require(role: Role):
    def dep(principal: Principal | None = Depends(viewer_or_demo)) -> Principal | None:
        if principal is None:
            if role == Role.VIEWER:
                return None
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
        if principal.role.rank < role.rank:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role {role.value} or higher")
        return principal
    return dep


def mutation(role: Role, *, allow_direct_demo: bool = False, direct_demo_role: Role | None = None):
    """Authenticated, role-checked, same-origin, CSRF-protected and rate-limited state change."""

    def dep(request: Request, state: AppState = Depends(get_state)) -> Principal:
        found = resolve_session(state.db, request.cookies.get(SESSION_COOKIE))
        direct = found is None and allow_direct_demo and state.settings.direct_demo
        if direct and not is_loopback_client(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "direct demo mode is limited to loopback clients")
        if found is None and not direct:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
        principal = Principal(*found) if found is not None else direct_demo_principal()
        if not origin_ok(request.headers, _same_origin(request, state)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-origin request refused")
        if not direct and not csrf_ok(principal.session.csrf_token, request.headers.get(CSRF_HEADER)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "missing or invalid CSRF token")
        if not state.limiter.allow(f"mut:{principal.username}:{client_key(request)}",
                                   state.settings.mutations_per_minute):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")
        direct_role_allowed = direct and direct_demo_role is not None and principal.role == direct_demo_role
        if principal.role.rank < role.rank and not direct_role_allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role {role.value} or higher")
        return principal
    return dep


def same_origin_only(request: Request, state: AppState = Depends(get_state)) -> None:
    if not origin_ok(request.headers, _same_origin(request, state)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-origin request refused")
