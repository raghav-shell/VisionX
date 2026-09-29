"""Web security primitives: sessions, CSRF/Origin checks, rate limiting, security headers, body limits.

* Session tokens are 256-bit random values; only their SHA-256 is stored. Cookies are HttpOnly,
  SameSite=Strict, Secure (unless explicitly disabled for plain-HTTP localhost development) and path-scoped.
* Every state-changing request needs the per-session CSRF token in ``X-CSRF-Token`` and, when the browser sends
  an ``Origin`` (or ``Referer``), it must be one of this server's origins.
* Login and mutation endpoints are rate limited per client address.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..storage import Database, Session, User

SESSION_COOKIE = "vs_session"
CSRF_HEADER = "x-csrf-token"
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Database, user: User, client: str, ttl_minutes: int) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with db.session() as s:
        s.query(Session).filter(Session.expires_at < now).delete()
        s.add(Session(token_hash=token_hash(token), user_id=user.id, csrf_token=csrf, client=client[:64],
                      expires_at=now + timedelta(minutes=ttl_minutes)))
    return token, csrf


def resolve_session(db: Database, token: str | None) -> tuple[User, Session] | None:
    if not token or len(token) > 128:
        return None
    with db.session() as s:
        sess = s.get(Session, token_hash(token))
        if sess is None:
            return None
        expires = sess.expires_at if sess.expires_at.tzinfo else sess.expires_at.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            s.delete(sess)
            return None
        user = s.get(User, sess.user_id)
        if user is None or user.disabled:
            return None
        return user, sess


def drop_session(db: Database, token: str | None) -> None:
    if token:
        with db.session() as s:
            sess = s.get(Session, token_hash(token))
            if sess is not None:
                s.delete(sess)


def csrf_ok(expected: str, presented: str | None) -> bool:
    return bool(presented) and hmac.compare_digest(expected.encode(), presented.encode())


def origin_ok(headers, allowed: set[str]) -> bool:
    """Reject cross-site requests: Origin (or Referer) must be one of this server's origins when present."""
    origin = headers.get("origin")
    if origin is None:
        ref = headers.get("referer")
        if ref is None:
            return True  # non-browser client; the CSRF token still applies
        parts = urlsplit(ref)
        origin = f"{parts.scheme}://{parts.netloc}"
    return origin in allowed


class RateLimiter:
    """Token bucket per key; thread-safe."""

    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, per_minute: int) -> bool:
        now = time.monotonic()
        rate = per_minute / 60.0
        with self._lock:
            tokens, last = self._buckets.get(key, (float(per_minute), now))
            tokens = min(float(per_minute), tokens + (now - last) * rate)
            if tokens < 1.0:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1.0, now)
            if len(self._buckets) > 10_000:
                self._buckets.clear()
            return True


class SecurityHeaders:
    """Pure ASGI middleware adding defensive headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope["path"].startswith("/api")

        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in (
                    b"server", b"x-powered-by")]
                present = {k.lower() for k, _ in headers}
                add = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"no-referrer",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=(), payment=(), usb=()",
                    b"cross-origin-opener-policy": b"same-origin",
                    b"cross-origin-resource-policy": b"same-origin",
                }
                if is_api:
                    add[b"cache-control"] = b"no-store"
                    add[b"content-security-policy"] = API_CSP.encode()
                for k, v in add.items():
                    if k not in present:
                        headers.append((k, v))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, wrapped)


class BodyLimit:
    """Reject request bodies above a limit (checked on Content-Length and while streaming)."""

    def __init__(self, app: ASGIApp, default_limit: int, upload_limit: int, upload_prefix: str = "/api/assets/upload"):
        self.app, self.default_limit, self.upload_limit, self.upload_prefix = app, default_limit, upload_limit, upload_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.upload_limit if scope["path"].startswith(self.upload_prefix) else self.default_limit
        for k, v in scope.get("headers", []):
            if k == b"content-length" and v.isdigit() and int(v) > limit:
                await _reject(send, 413, b'{"detail":"request body too large"}')
                return
        seen = 0

        async def limited() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise _TooLarge()
            return message

        try:
            await self.app(scope, limited, send)
        except _TooLarge:
            await _reject(send, 413, b'{"detail":"request body too large"}')


class _TooLarge(Exception):
    pass


async def _reject(send: Send, status: int, body: bytes) -> None:
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})
