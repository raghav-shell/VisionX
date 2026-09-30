"""Pickle-free framing shared by the sandbox parent and worker: length-prefixed JSON + .npy frames."""

from __future__ import annotations

import io
import json
import os
import select
import struct
import time

import numpy as np

try:
    import _winapi
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None

MAX_FRAME_BYTES = 1 << 30
_LEN = struct.Struct(">Q")


def _wait_readable(fd: int, timeout: float) -> bool:
    """True once ``fd`` has data (or its writer has gone), False if ``timeout`` passes first."""
    if msvcrt is None:
        ready, _, _ = select.select([fd], [], [], timeout)
        return bool(ready)
    # select() only accepts sockets on Windows, so poll the pipe. A closed writer raises
    # BrokenPipeError here, which callers already treat as a dead worker.
    handle = msvcrt.get_osfhandle(fd)
    end = time.monotonic() + timeout
    while True:
        available, _ = _winapi.PeekNamedPipe(handle, 0)
        if available:
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(0.002)


def dump_array(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, np.ascontiguousarray(arr), allow_pickle=False)
    return buf.getvalue()


def load_array(data: bytes) -> np.ndarray:
    return np.load(io.BytesIO(data), allow_pickle=False)


def write_frame(fd: int, payload: bytes) -> None:
    view = memoryview(_LEN.pack(len(payload)) + payload)
    while view:
        n = os.write(fd, view)
        view = view[n:]


def read_exact(fd: int, n: int, deadline: float | None) -> bytes:
    chunks = []
    remaining = n
    while remaining:
        if deadline is not None:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError
            if not _wait_readable(fd, left):
                raise TimeoutError
        chunk = os.read(fd, min(remaining, 1 << 20))
        if not chunk:
            raise EOFError
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(fd: int, deadline: float | None, max_bytes: int = MAX_FRAME_BYTES) -> bytes:
    (size,) = _LEN.unpack(read_exact(fd, _LEN.size, deadline))
    if size > max_bytes:
        raise ValueError(f"frame of {size} bytes exceeds limit")
    return read_exact(fd, size, deadline)


def send_message(fd: int, header: dict, arrays: list[np.ndarray] | None = None, raw: bytes | None = None) -> None:
    arrays = arrays or []
    write_frame(fd, json.dumps({**header, "n_arrays": len(arrays), "raw": raw is not None}).encode())
    if raw is not None:
        write_frame(fd, raw)
    for a in arrays:
        write_frame(fd, dump_array(a))


def recv_message(fd: int, deadline: float | None, max_bytes: int = MAX_FRAME_BYTES
                 ) -> tuple[dict, list[np.ndarray], bytes | None]:
    header = json.loads(read_frame(fd, deadline, 1 << 20).decode())
    if not isinstance(header, dict):
        raise ValueError("malformed header")
    raw = read_frame(fd, deadline, max_bytes) if header.get("raw") else None
    arrays = [load_array(read_frame(fd, deadline, max_bytes)) for _ in range(int(header.get("n_arrays", 0)))]
    return header, arrays, raw
