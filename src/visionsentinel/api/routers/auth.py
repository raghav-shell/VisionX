"""Authentication: login, logout, current principal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ... import __version__
from ...contracts import Role
from ...governance import authenticate
from ..deps import Principal, client_key, current_principal, get_state, mutation, same_origin_only
from ..security import SESSION_COOKIE, create_session, drop_session
from ..state import AppState

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def user_view(u) -> dict:
    return {"username": u.username, "display_name": u.display_name, "role": u.role}


@router.post("/login", dependencies=[Depends(same_origin_only)])
def login(body: LoginBody, request: Request, response: Response, state: AppState = Depends(get_state)) -> dict:
    ip = client_key(request)
    limit = state.settings.login_attempts_per_minute
    if not (state.limiter.allow(f"login-ip:{ip}", limit * 3) and state.limiter.allow(f"login-user:{body.username}", limit)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many login attempts; wait a minute")
    user = authenticate(state.db, body.username, body.password)
    if user is None:
        state.audit.record(body.username[:64], "login_failed", "session", justification=f"client {ip}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid username or password")
    token, csrf = create_session(state.db, user, ip, state.settings.session_ttl_minutes)
    response.set_cookie(SESSION_COOKIE, token, max_age=state.settings.session_ttl_minutes * 60, httponly=True,
                        secure=state.settings.secure_cookies, samesite="strict", path="/")
    state.audit.record(user.username, "login", "session", justification=f"client {ip}")
    return {"user": user_view(user), "csrf": csrf}


@router.post("/logout")
def logout(request: Request, response: Response, principal: Principal = Depends(mutation(Role.VIEWER)),
           state: AppState = Depends(get_state)) -> dict:
    drop_session(state.db, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/", secure=state.settings.secure_cookies, httponly=True,
                           samesite="strict")
    state.audit.record(principal.username, "logout", "session")
    return {"ok": True}


@router.get("/me")
def me(principal: Principal = Depends(current_principal), state: AppState = Depends(get_state)) -> dict:
    return {"user": user_view(principal.user), "csrf": principal.session.csrf_token,
            "demo_mode": state.settings.demo_mode, "version": __version__}
