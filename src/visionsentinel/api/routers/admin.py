"""Admin-only local account lifecycle API.

Passwords are accepted only for create/reset operations, hashed before persistence,
and never included in any response or audit record.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from ...contracts import Role
from ...core.errors import GovernanceError
from ...governance.identity import MIN_PASSWORD, create_user, hash_password
from ...storage import Session, User
from ..deps import Principal, get_state, mutation
from ..state import AppState

router = APIRouter(prefix="/api/admin", tags=["admin"])


class CreateUserBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=MIN_PASSWORD, max_length=256)
    role: Role
    display_name: str | None = Field(default=None, max_length=128)


class RoleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role


class ResetPasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=MIN_PASSWORD, max_length=256)


def user_view(user: User) -> dict:
    """Return the public account representation; password hashes stay server-only."""
    return {
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "disabled": user.disabled,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _get_user(session, username: str) -> User:
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"user {username!r} not found")
    return user


@router.get("/users")
def list_users(
    _: Principal = Depends(mutation(Role.ADMIN)),
    state: AppState = Depends(get_state),
) -> dict:
    with state.db.session() as session:
        users = session.scalars(select(User).order_by(User.username)).all()
        return {"total": len(users), "users": [user_view(user) for user in users]}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_managed_user(
    body: CreateUserBody,
    principal: Principal = Depends(mutation(Role.ADMIN)),
    state: AppState = Depends(get_state),
) -> dict:
    try:
        user = create_user(state.db, body.username, body.password, body.role, body.display_name)
    except GovernanceError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    state.audit.record(principal.username, "admin_create_user", user.username, new=user.role)
    return {"user": user_view(user)}


@router.patch("/users/{username}/role")
def update_user_role(
    username: str,
    body: RoleBody,
    principal: Principal = Depends(mutation(Role.ADMIN)),
    state: AppState = Depends(get_state),
) -> dict:
    with state.db.session() as session:
        user = _get_user(session, username)
        previous_role = user.role
        user.role = body.role.value
        view = user_view(user)
    state.audit.record(principal.username, "admin_change_role", username, old=previous_role, new=body.role.value)
    return {"user": view}


def _set_disabled(username: str, disabled: bool, principal: Principal, state: AppState) -> dict:
    with state.db.session() as session:
        user = _get_user(session, username)
        previous = user.disabled
        user.disabled = disabled
        # Disabling an account invalidates every extant authenticated session.
        if disabled:
            session.execute(delete(Session).where(Session.user_id == user.id))
        view = user_view(user)
    action = "admin_disable_user" if disabled else "admin_enable_user"
    state.audit.record(principal.username, action, username, old="disabled" if previous else "active",
                       new="disabled" if disabled else "active")
    return {"user": view}


@router.post("/users/{username}/disable")
def disable_user(
    username: str,
    principal: Principal = Depends(mutation(Role.ADMIN)),
    state: AppState = Depends(get_state),
) -> dict:
    return _set_disabled(username, True, principal, state)


@router.post("/users/{username}/enable")
def enable_user(
    username: str,
    principal: Principal = Depends(mutation(Role.ADMIN)),
    state: AppState = Depends(get_state),
) -> dict:
    return _set_disabled(username, False, principal, state)


@router.post("/users/{username}/reset-password")
def reset_password(
    username: str,
    body: ResetPasswordBody,
    principal: Principal = Depends(mutation(Role.ADMIN)),
    state: AppState = Depends(get_state),
) -> dict:
    with state.db.session() as session:
        user = _get_user(session, username)
        user.password_hash = hash_password(body.password)
        # Force all old sessions to authenticate with the newly issued secret.
        session.execute(delete(Session).where(Session.user_id == user.id))
        view = user_view(user)
    state.audit.record(principal.username, "admin_reset_password", username)
    return {"user": view}
