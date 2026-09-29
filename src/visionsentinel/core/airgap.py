"""Egress guard: prove that a code path makes no outbound network access.

Every high-level client (urllib, http.client, requests, httpx, aiohttp, asyncio) ultimately
resolves names through ``socket.getaddrinfo`` and connects through ``socket.socket.connect``. The
guard wraps those primitives (plus ``create_connection``, ``connect_ex``, ``sendto`` and the legacy
``gethostbyname`` family) and raises :class:`EgressViolation` for any non-loopback destination.
Unix-domain sockets and loopback addresses remain allowed.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field

_LOOPBACK_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}


class EgressViolation(RuntimeError):
    pass


@dataclass
class EgressRecord:
    attempts: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, what: str) -> None:
        with self.lock:
            self.attempts.append(what)


def _is_loopback_host(host: object) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    host = str(host).strip("[]").split("%", 1)[0]
    if host.lower() in _LOOPBACK_NAMES or host == "":
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_unspecified


def _check_address(family: int, address: object, record: EgressRecord | None, op: str) -> None:
    if family == getattr(socket, "AF_UNIX", object()):
        return
    host = address[0] if isinstance(address, tuple) and address else address
    if not _is_loopback_host(host):
        msg = f"blocked outbound {op} to {host!r}"
        if record is not None:
            record.add(msg)
        raise EgressViolation(msg)


@contextmanager
def egress_guard(record: EgressRecord | None = None):
    """Block all non-loopback network access inside the ``with`` block (process-wide)."""
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_sendto = socket.socket.sendto
    orig_create = socket.create_connection
    orig_getaddrinfo = socket.getaddrinfo
    orig_gethostbyname = socket.gethostbyname
    orig_gethostbyname_ex = socket.gethostbyname_ex

    def connect(self, address):  # type: ignore[no-untyped-def]
        _check_address(self.family, address, record, "connect")
        return orig_connect(self, address)

    def connect_ex(self, address):  # type: ignore[no-untyped-def]
        _check_address(self.family, address, record, "connect")
        return orig_connect_ex(self, address)

    def sendto(self, data, *args):  # type: ignore[no-untyped-def]
        address = args[-1]
        _check_address(self.family, address, record, "sendto")
        return orig_sendto(self, data, *args)

    def create_connection(address, *args, **kwargs):  # type: ignore[no-untyped-def]
        _check_address(socket.AF_INET, address, record, "connect")
        return orig_create(address, *args, **kwargs)

    def getaddrinfo(host, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not _is_loopback_host(host):
            msg = f"blocked DNS resolution of {host!r}"
            if record is not None:
                record.add(msg)
            raise EgressViolation(msg)
        return orig_getaddrinfo(host, *args, **kwargs)

    def gethostbyname(host):  # type: ignore[no-untyped-def]
        if not _is_loopback_host(host):
            msg = f"blocked DNS resolution of {host!r}"
            if record is not None:
                record.add(msg)
            raise EgressViolation(msg)
        return orig_gethostbyname(host)

    def gethostbyname_ex(host):  # type: ignore[no-untyped-def]
        if not _is_loopback_host(host):
            msg = f"blocked DNS resolution of {host!r}"
            if record is not None:
                record.add(msg)
            raise EgressViolation(msg)
        return orig_gethostbyname_ex(host)

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    socket.socket.sendto = sendto  # type: ignore[method-assign]
    socket.create_connection = create_connection  # type: ignore[assignment]
    socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]
    socket.gethostbyname = gethostbyname  # type: ignore[assignment]
    socket.gethostbyname_ex = gethostbyname_ex  # type: ignore[assignment]
    try:
        yield record
    finally:
        socket.socket.connect = orig_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = orig_connect_ex  # type: ignore[method-assign]
        socket.socket.sendto = orig_sendto  # type: ignore[method-assign]
        socket.create_connection = orig_create  # type: ignore[assignment]
        socket.getaddrinfo = orig_getaddrinfo  # type: ignore[assignment]
        socket.gethostbyname = orig_gethostbyname  # type: ignore[assignment]
        socket.gethostbyname_ex = orig_gethostbyname_ex  # type: ignore[assignment]


@contextmanager
def workload_airgap(record: EgressRecord | None = None):
    """Apply offline library settings and the egress policy to one workload."""
    pin_offline_environment()
    with egress_guard(record) as active_record:
        yield active_record


def non_loopback_probe_host() -> str:
    """Return a policy-derived address suitable for proving egress rejection."""
    network = ipaddress.ip_network("0.0.0.0/0")
    return next(str(address) for address in network.hosts() if not _is_loopback_host(address))


def pin_offline_environment() -> None:
    """Defence in depth: tell third-party libraries never to reach model hubs."""
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE", "NEXT_TELEMETRY_DISABLED",
                "DO_NOT_TRACK"):
        os.environ.setdefault(key, "1")
    os.environ.setdefault("TORCH_HOME", os.path.join(os.environ.get("VISIONSENTINEL_HOME", "var"), "torch-home"))
