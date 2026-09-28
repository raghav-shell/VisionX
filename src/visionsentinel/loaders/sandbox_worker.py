"""Sandboxed model worker (child side). Started as ``python -I -B -m visionsentinel.loaders.sandbox_worker``.

See :mod:`visionsentinel.loaders.models.sandbox` for the isolation measures. The network namespace is
entered before anything else is imported: ``unshare(CLONE_NEWUSER)`` requires a single-threaded
process, and NumPy/BLAS start threads at import time.
"""

from __future__ import annotations

import os


def _enter_namespaces() -> str:
    uid, gid = os.getuid(), os.getgid()
    try:
        os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNET)  # type: ignore[attr-defined]
    except (AttributeError, OSError) as exc:
        return f"unavailable on this host ({type(exc).__name__}: {exc}); audit hook still blocks sockets"
    try:  # map our own uid/gid so module files stay readable inside the namespace
        with open("/proc/self/setgroups", "w") as fh:
            fh.write("deny")
        with open("/proc/self/uid_map", "w") as fh:
            fh.write(f"0 {uid} 1")
        with open("/proc/self/gid_map", "w") as fh:
            fh.write(f"0 {gid} 1")
    except OSError as exc:
        return f"isolated, but uid map failed ({exc})"
    return "isolated (new network namespace: no interfaces)"


NAMESPACE_STATUS = _enter_namespaces()

import io  # noqa: E402 - intentionally after namespace entry
import socket  # noqa: E402 - imported before the audit hook (the probe creates sockets)
import subprocess  # noqa: E402 - imported before the audit hook (the probe starts a process)
import resource  # noqa: E402
import signal  # noqa: E402
import sys  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402

from .sandbox_protocol import recv_message, send_message  # noqa: E402

_BLOCKED_EVENTS = ("socket.", "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork",
                   "os.forkpty", "pty.spawn", "ctypes.dlopen", "ctypes.dlsym", "os.remove", "os.rename", "os.rmdir",
                   "os.chmod", "os.mkdir", "shutil.rmtree", "os.truncate", "webbrowser.open")


def _isolate(cfg: dict) -> dict[str, Any]:
    info: dict[str, Any] = {"process": "separate isolated interpreter (python -I -B)",
                            "network_namespace": NAMESPACE_STATUS}
    for name, key in (("RLIMIT_AS", "memory_bytes"), ("RLIMIT_CPU", "cpu_seconds")):
        try:
            resource.setrlimit(getattr(resource, name), (int(cfg[key]), int(cfg[key])))
            info[name.lower()] = int(cfg[key])
        except (ValueError, OSError) as exc:
            info[name.lower()] = f"not applied: {exc}"
    return info


def _lock_down(info: dict[str, Any]) -> None:
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    try:
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        info["rlimit_fsize"] = 0
    except (ValueError, OSError) as exc:
        info["rlimit_fsize"] = f"not applied: {exc}"

    def hook(event: str, args: tuple) -> None:
        if event == "open" or event.startswith(_BLOCKED_EVENTS):
            raise PermissionError(f"VisionSentinel sandbox blocked '{event}'")

    sys.addaudithook(hook)
    info["audit_hook"] = "sockets, process creation, dlopen, file open and file mutation blocked"


def _probe_isolation() -> dict[str, str]:
    """Attempt forbidden actions and report how each was stopped (used by tests and the self-test)."""
    results: dict[str, str] = {}

    def attempt(name: str, fn) -> None:
        try:
            fn()
            results[name] = "ALLOWED"
        except PermissionError as exc:
            results[name] = f"blocked: {exc}"
        except OSError as exc:
            results[name] = f"blocked by kernel: {exc.strerror or exc}"


    attempt("socket", lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM))
    attempt("file_write", lambda: open("/tmp/visionsentinel-sandbox-probe", "w"))  # noqa: SIM115
    attempt("file_read", lambda: open("/etc/hostname"))  # noqa: SIM115
    attempt("process", lambda: subprocess.Popen(["true"]).wait())  # noqa: S603,S607 - must be blocked

    results["network_namespace"] = NAMESPACE_STATUS
    return results


def _flatten_state(obj: Any, prefix: str = "") -> dict[str, Any]:
    import torch

    out: dict[str, Any] = {}
    if isinstance(obj, torch.Tensor):
        out[prefix or "tensor"] = obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten_state(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.update(_flatten_state(v, f"{prefix}.{i}" if prefix else str(i)))
    return out


def main() -> None:  # pragma: no cover - exercised through SandboxWorker in a child process
    proto_in = os.dup(0)
    proto_out = os.dup(1)
    os.dup2(2, 1)  # anything a library prints goes to stderr, never into the protocol stream
    header, _, model_bytes = recv_message(proto_in, None)
    cfg = header["config"]
    backend = cfg["backend"]
    options = cfg.get("options", {})
    info = _isolate(cfg)
    session = model = state = None
    try:
        if backend == "onnxruntime":
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = int(options.get("threads", 2))
            opts.inter_op_num_threads = 1
            opts.log_severity_level = 3
            _lock_down(info)
            session = ort.InferenceSession(model_bytes, sess_options=opts, providers=["CPUExecutionProvider"])
            in_name, out_name = session.get_inputs()[0].name, session.get_outputs()[0].name
            info["inputs"] = [{"name": i.name, "shape": [str(d) for d in i.shape], "type": i.type}
                              for i in session.get_inputs()]
            info["outputs"] = [{"name": o.name, "shape": [str(d) for d in o.shape]} for o in session.get_outputs()]
        else:
            import torch

            from .models.architectures import build_torch_module
            from .models.recon_torch import ReconCNN  # noqa: F401 - imported before the hook forbids file access

            torch.set_num_threads(int(options.get("threads", 2)))
            # Pre-warm lazily imported deserialisation machinery while imports are still allowed.
            warm = io.BytesIO()
            torch.save({"w": torch.zeros(1)}, warm)
            torch.load(io.BytesIO(warm.getvalue()), map_location="cpu", weights_only=True)
            _lock_down(info)
            buf = io.BytesIO(model_bytes)
            if backend == "torchscript":
                model = torch.jit.load(buf, map_location="cpu")
                model.eval()
                info["has_features"] = hasattr(model, "features")
                info["graph_ops"] = [n.kind() for n in model.inlined_graph.nodes()]
                info["parameters"] = {k: list(v.shape) for k, v in model.state_dict().items()}
            elif backend == "state_dict":
                state = _flatten_state(torch.load(buf, map_location="cpu", weights_only=True))
                info["parameters"] = {k: list(v.shape) for k, v in state.items()}
                if options.get("architecture"):
                    model = build_torch_module(options["architecture"], int(options["num_classes"]))
                    model.load_state_dict(state, strict=True)
                    model.eval()
                    info["has_features"] = True
            else:
                raise ValueError(f"unknown backend {backend}")
        send_message(proto_out, {"ok": True, "info": info})
    except BaseException as exc:  # noqa: BLE001 - reported to the parent
        send_message(proto_out, {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:2000], "info": info})
        return

    while True:
        try:
            req, arrays, _ = recv_message(proto_in, None)
        except EOFError:
            return
        op = req.get("op")
        try:
            if op == "shutdown":
                send_message(proto_out, {"ok": True})
                return
            if op == "logits":
                if session is not None:
                    out = session.run([out_name], {in_name: arrays[0].astype(np.float32)})[0]
                else:
                    import torch
                    with torch.no_grad():
                        out = model(torch.from_numpy(arrays[0].astype(np.float32))).numpy()
                send_message(proto_out, {"ok": True}, [np.asarray(out, dtype=np.float32)])
            elif op == "features":
                import torch
                with torch.no_grad():
                    out = model.features(torch.from_numpy(arrays[0].astype(np.float32))).numpy()
                send_message(proto_out, {"ok": True}, [np.asarray(out, dtype=np.float32).reshape(len(out), -1)])
            elif op == "loss_grad":
                import torch
                x = torch.from_numpy(arrays[0].astype(np.float32)).requires_grad_(True)
                mean = torch.tensor(req["mean"], dtype=torch.float32).view(1, 3, 1, 1)
                std = torch.tensor(req["std"], dtype=torch.float32).view(1, 3, 1, 1)
                logits = model((x - mean) / std)
                target = torch.full((len(x),), int(req["target"]), dtype=torch.long)
                loss = torch.nn.functional.cross_entropy(logits, target)
                loss.backward()
                send_message(proto_out, {"ok": True, "loss": float(loss.item())}, [x.grad.numpy()])
            elif op == "probe_isolation":
                send_message(proto_out, {"ok": True, "result": _probe_isolation()})
            elif op == "params":
                sd = model.state_dict() if model is not None else state
                names = sorted(sd)[: int(req.get("limit", 4096))]
                send_message(proto_out, {"ok": True, "names": names}, [sd[n].detach().cpu().numpy() for n in names])
            else:
                send_message(proto_out, {"ok": False, "error": f"unknown op {op!r}"})
        except BaseException as exc:  # noqa: BLE001
            send_message(proto_out, {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:2000]})


if __name__ == "__main__":  # pragma: no cover
    main()
