"""Sandboxed model worker (parent side).

Untrusted model bytes are only ever handed to native runtimes (onnxruntime, TorchScript,
``torch.load(weights_only=True)``) inside a separate, freshly started interpreter
(``python -I -B -m visionsentinel.loaders.sandbox_worker``) that, before touching the model:

* tries to enter a fresh user + network namespace (no network interfaces at all) when the host allows
  unprivileged namespaces, and records whether it succeeded;
* sets ``RLIMIT_AS`` (address space), ``RLIMIT_CPU`` and ``RLIMIT_FSIZE = 0`` (no file can be written,
  enforced by the kernel for native code as well);
* installs a Python audit hook that refuses sockets, process creation, ``ctypes`` library loading and
  every ``open()`` — the worker receives the model as bytes and never needs the file system.

The channel is pickle-free: length-prefixed frames holding a JSON header followed by ``.npy`` blobs
parsed with ``allow_pickle=False`` and bounded in size, so a compromised worker cannot inject objects
into the parent.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from ...core.errors import SandboxError
from ..sandbox_protocol import recv_message, send_message

@dataclass
class SandboxLimits:
    memory_bytes: int
    cpu_seconds: int
    call_timeout_s: float
    max_model_bytes: int


class SandboxWorker:
    def __init__(self, backend: str, model_bytes: bytes, limits: SandboxLimits, options: dict | None = None) -> None:
        self.limits = limits
        config = {"backend": backend, "memory_bytes": limits.memory_bytes, "cpu_seconds": limits.cpu_seconds,
                  "max_model_bytes": limits.max_model_bytes, "options": options or {}}
        env = {"PATH": os.environ.get("PATH", "/usr/bin"), "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1",
               "MKL_NUM_THREADS": "1", "HF_HUB_OFFLINE": "1", "PYTHONHASHSEED": "0"}
        self.proc = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-I", "-B", "-m", "visionsentinel.loaders.sandbox_worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, close_fds=True)
        self._stderr: list[bytes] = []
        self._drain = threading.Thread(target=self._drain_stderr, daemon=True)
        self._drain.start()
        self._in, self._out = self.proc.stdin.fileno(), self.proc.stdout.fileno()  # type: ignore[union-attr]
        try:
            send_message(self._in, {"op": "load", "config": config}, raw=model_bytes)
        except OSError as exc:
            self.close()
            raise SandboxError(f"sandboxed {backend} worker failed to start: {self.stderr_tail()}") from exc
        header, _ = self._reply(timeout=max(90.0, limits.call_timeout_s))
        self.info: dict = header.get("info", {})
        if not header.get("ok"):
            self.close()
            raise SandboxError(f"sandboxed {backend} worker refused the model: {header.get('error')}")

    def _drain_stderr(self) -> None:
        stream = self.proc.stderr
        total = 0
        while stream is not None:
            chunk = stream.read(4096)
            if not chunk:
                return
            if total < 64 * 1024:
                self._stderr.append(chunk)
                total += len(chunk)

    def stderr_tail(self) -> str:
        return b"".join(self._stderr)[-1500:].decode("utf-8", "replace").strip()

    def _reply(self, timeout: float) -> tuple[dict, list[np.ndarray]]:
        try:
            header, arrays, _ = recv_message(self._out, time.monotonic() + timeout)
        except TimeoutError:
            self.close()
            raise SandboxError(f"sandboxed worker did not answer within {timeout:.0f}s and was terminated") from None
        except (EOFError, OSError, ValueError) as exc:
            self.proc.poll()
            code = self.proc.returncode
            self.close()
            raise SandboxError(f"sandboxed worker died (exit code {code}): {self.stderr_tail()[-400:]}") from exc
        return header, arrays

    def call(self, op: str, arrays: list[np.ndarray] | None = None, **params: Any) -> tuple[dict, list[np.ndarray]]:
        if self.proc.poll() is not None:
            raise SandboxError(f"sandboxed worker is not running (exit code {self.proc.returncode})")
        try:
            send_message(self._in, {"op": op, **params}, arrays or [])
        except OSError as exc:
            raise SandboxError(f"sandboxed worker pipe closed: {self.stderr_tail()[-400:]}") from exc
        header, out = self._reply(self.limits.call_timeout_s)
        if not header.get("ok"):
            raise SandboxError(f"sandboxed worker error during '{op}': {header.get('error')}")
        return header, out

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                send_message(self._in, {"op": "shutdown"})
                self.proc.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
                self.proc.wait(timeout=3)
        for stream in (self.proc.stdin, self.proc.stdout):
            try:
                if stream:
                    stream.close()
            except OSError:
                pass

    def __del__(self) -> None:  # pragma: no cover - best effort
        try:
            if self.proc.poll() is None:
                self.proc.kill()
        except Exception:  # noqa: BLE001
            pass
