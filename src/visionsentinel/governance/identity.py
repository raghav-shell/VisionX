"""Users and password hashing.

Argon2id (argon2-cffi, RFC 9106 parameters) is preferred; scrypt (hashlib, N=2^15, r=8, p=1) is the fallback
when argon2-cffi is unavailable. Plain or fast hashes are never used. Verification is constant-time and
unknown users still pay the hashing cost, so timing does not reveal which usernames exist.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import uuid

from sqlalchemy import select

from ..contracts import Role
from ..core.errors import AuthorizationError, GovernanceError
from ..storage import Database, User

try:  # pragma: no cover - import guard
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

    _ARGON = PasswordHasher()
except ImportError:  # pragma: no cover
    _ARGON = None

USERNAME = re.compile(r"^[a-z][a-z0-9._-]{2,31}$")
MIN_PASSWORD = 10
_DUMMY = None


def hash_password(password: str) -> str:
    if _ARGON is not None:
        return _ARGON.hash(password)
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**15, r=8, p=1, maxmem=64 * 1024 * 1024)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(stored: str, password: str) -> bool:
    if stored.startswith("scrypt$"):
        _, salt, dk = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=2**15, r=8, p=1,
                             maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(got, base64.b64decode(dk))
    if _ARGON is None:  # pragma: no cover
        return False
    try:
        return _ARGON.verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _dummy_hash() -> str:
    global _DUMMY
    if _DUMMY is None:
        _DUMMY = hash_password(os.urandom(8).hex())
    return _DUMMY


def create_user(db: Database, username: str, password: str, role: Role, display_name: str | None = None) -> User:
    if not USERNAME.match(username):
        raise GovernanceError("username must be 3–32 characters: lowercase letters, digits, '.', '_' or '-'")
    if len(password) < MIN_PASSWORD:
        raise GovernanceError(f"password must be at least {MIN_PASSWORD} characters")
    with db.session() as s:
        if s.scalar(select(User).where(User.username == username)):
            raise GovernanceError(f"user {username!r} already exists")
        user = User(id=str(uuid.uuid4()), username=username, display_name=display_name or username, role=role.value,
                    password_hash=hash_password(password))
        s.add(user)
    return user


def authenticate(db: Database, username: str, password: str) -> User | None:
    with db.session() as s:
        user = s.scalar(select(User).where(User.username == username))
        if user is None or user.disabled:
            verify_password(_dummy_hash(), password)  # equalise timing
            return None
        return user if verify_password(user.password_hash, password) else None


def require_role(user: User, minimum: Role) -> None:
    if Role(user.role).rank < minimum.rank:
        raise AuthorizationError(f"role {user.role} may not perform this action (requires {minimum.value} or higher)")
