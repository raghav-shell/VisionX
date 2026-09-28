"""Model loading with format detection.

    .onnx                 → ONNX (parsed as data; inference sandboxed; verified differentiable interpreter)
    TorchScript zip       → executed only in the sandbox
    PyTorch state dict    → ``torch.load(weights_only=True)`` only in the sandbox; executable with a known architecture
    .safetensors          → pure-data parser; executable with a known architecture

Unknown formats — including pickle files that are not PyTorch archives — are refused.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from ...core.errors import LoaderError
from ...core.hashing import sha256_digest
from ...core.limits import ResourceLimits
from ..safe_io import read_bounded
from .base import GraphSummary, ModelHandle, PreprocessConfig, load_preprocess, parameter_digest, preprocess, softmax


def detect_model_format(path: Path, data: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix == ".onnx":
        return "onnx"
    if suffix == ".safetensors":
        return "safetensors"
    if data[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
        if any("/code/" in n or n.startswith("code/") for n in names) or any(n.endswith("constants.pkl") for n in names):
            return "torchscript"
        if any(n.endswith("data.pkl") for n in names):
            return "state_dict"
    if data[:2] in (b"\x80\x02", b"\x80\x04", b"\x80\x05"):
        return "state_dict"
    if suffix in (".pt", ".pth"):
        return "state_dict"
    raise LoaderError(f"{path.name}: unrecognised model format",
                      hint="supported: .onnx, TorchScript archives, PyTorch state dicts, .safetensors")


def open_model(path: str | Path, limits: ResourceLimits | None = None, *, preprocess_path: Path | None = None,
               architecture: str | None = None, name: str | None = None) -> ModelHandle:
    from .backends import OnnxModel, SafetensorsModel, TorchWorkerModel

    limits = limits or ResourceLimits()
    path = Path(path)
    if not path.is_file():
        raise LoaderError(f"model file {path} not found")
    data = read_bounded(path, limits.max_model_bytes)
    digest = sha256_digest(data)
    sidecar = path.with_name(path.stem + ".preprocess.json")
    cfg_path = preprocess_path or (sidecar if sidecar.is_file() else None)
    cfg = load_preprocess(cfg_path) if cfg_path else None
    fmt = detect_model_format(path, data)
    label = name or path.stem
    if fmt == "onnx":
        return OnnxModel(label, path, data, digest, cfg, limits)
    if fmt == "safetensors":
        return SafetensorsModel(label, path, data, digest, cfg, limits, architecture=architecture)
    return TorchWorkerModel(label, path, data, digest, cfg, limits, backend=fmt, architecture=architecture,
                            num_classes=len(cfg.class_names) if cfg else None)


__all__ = ["GraphSummary", "ModelHandle", "PreprocessConfig", "load_preprocess", "open_model", "parameter_digest",
           "preprocess", "softmax", "detect_model_format"]
