"""FastAPI dependencies: application state, authenticated principal, role and CSRF enforcement."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from ..contracts import Role
from ..storage import Session, User
from .security import CSRF_HEADER, SESSION_COOKIE, csrf_ok, origin_ok, resolve_session
from .state import AppState


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


def current_principal(request: Request, state: AppState = Depends(get_state)) -> Principal:
    found = resolve_session(state.db, request.cookies.get(SESSION_COOKIE))
    if found is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    return Principal(*found)


def _same_origin(request: Request, state: AppState) -> set[str]:
    host = request.headers.get("host", "")
    return {f"http://{host}", f"https://{host}", *state.settings.extra_origins}


def require(role: Role):
    def dep(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role.rank < role.rank:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role {role.value} or higher")
        return principal
    return dep


def mutation(role: Role):
    """Authenticated, role-checked, same-origin, CSRF-protected and rate-limited state change."""

    def dep(request: Request, state: AppState = Depends(get_state),
            principal: Principal = Depends(current_principal)) -> Principal:
        if not origin_ok(request.headers, _same_origin(request, state)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-origin request refused")
        if not csrf_ok(principal.session.csrf_token, request.headers.get(CSRF_HEADER)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "missing or invalid CSRF token")
        if not state.limiter.allow(f"mut:{principal.username}:{client_key(request)}",
                                   state.settings.mutations_per_minute):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")
        if principal.role.rank < role.rank:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role {role.value} or higher")
        return principal
    return dep


def same_origin_only(request: Request, state: AppState = Depends(get_state)) -> None:
    if not origin_ok(request.headers, _same_origin(request, state)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-origin request refused")
