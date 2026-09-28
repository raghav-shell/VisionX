"""Common model handle interface and the preprocessing contract.

Every backend exposes the same surface: artifact/parameter digests, a graph summary when the
format carries one, parameters when accessible, and prediction / features / input gradients when
the backend (and its fidelity checks) allow. Images enter as ``N×H×W×3`` uint8 and are preprocessed
exactly as declared by the :class:`PreprocessConfig`, whose digest is bound into provenance records.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from ...contracts import Capability
from ...core.errors import LoaderError
from ...core.hashing import digest_json
from ..safe_io import read_bounded


class PreprocessConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_size: int = Field(ge=8, le=1024)
    mean: tuple[float, float, float] = (0.0, 0.0, 0.0)
    std: tuple[float, float, float] = (1.0, 1.0, 1.0)
    resize: Literal["box", "bilinear"] = "box"
    output: Literal["logits", "probabilities"] = "logits"
    class_names: list[str] = Field(default_factory=list)

    @property
    def digest(self) -> str:
        return digest_json(self.model_dump(mode="json"))


def load_preprocess(path: Path) -> PreprocessConfig:
    data = read_bounded(path, 256 * 1024)
    try:
        return PreprocessConfig.model_validate(json.loads(data))
    except (ValueError, TypeError) as exc:
        raise LoaderError(f"{path.name}: invalid preprocessing config: {exc}") from exc


def preprocess(images: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """uint8 N×H×W×3 → float32 N×3×S×S in model input space."""
    s = cfg.input_size
    out = np.empty((len(images), 3, s, s), dtype=np.float32)
    mean = np.asarray(cfg.mean, dtype=np.float32)[:, None, None]
    std = np.asarray(cfg.std, dtype=np.float32)[:, None, None]
    method = Image.Resampling.BOX if cfg.resize == "box" else Image.Resampling.BILINEAR
    for i, img in enumerate(images):
        if img.shape[0] != s or img.shape[1] != s:
            img = np.asarray(Image.fromarray(img).resize((s, s), method))
        out[i] = (img.transpose(2, 0, 1).astype(np.float32) / 255.0 - mean) / std
    return out


def softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def parameter_digest(params: dict[str, np.ndarray]) -> str:
    """Canonical parameter digest: sorted names, dtype, shape and little-endian bytes."""
    h = hashlib.sha256(b"visionsentinel/params/v1\0")
    for name in sorted(params):
        arr = np.ascontiguousarray(params[name])
        h.update(name.encode() + b"\0" + str(arr.dtype.str).encode() + b"\0" + str(arr.shape).encode() + b"\0")
        h.update(arr.astype(arr.dtype.newbyteorder("<"), copy=False).tobytes())
    return "sha256:" + h.hexdigest()


@dataclass
class GraphSummary:
    """Format-independent description of a model's computation (for architecture fingerprints)."""

    kind: Literal["onnx-graph", "torchscript-graph", "parameter-shapes"]
    ops: list[dict[str, Any]] = field(default_factory=list)   # {op, inputs, outputs, attrs, params}
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    parameters: dict[str, tuple[int, ...]] = field(default_factory=dict)
    opset: int | None = None
    producer: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class BackendStatus:
    predict: bool = False
    logits: bool = False
    gradients: bool = False
    activations: bool = False
    parameters: bool = False
    graph: bool = False
    notes: list[str] = field(default_factory=list)


class ModelHandle:
    """Base class; backends override the capability-backed methods."""

    format: str = "unknown"

    def __init__(self, name: str, path: Path, artifact_digest: str, cfg: PreprocessConfig, *,
                 preprocess_explicit: bool) -> None:
        self.name = name
        self.path = path
        self.artifact_digest = artifact_digest
        self.cfg = cfg
        self.preprocess_explicit = preprocess_explicit
        self.status = BackendStatus()
        self._param_digest: str | None = None

    # ---------------------------------------------------------------- metadata
    @property
    def class_names(self) -> list[str]:
        return self.cfg.class_names

    @property
    def num_classes(self) -> int | None:
        return len(self.cfg.class_names) or None

    @property
    def has_activations(self) -> bool:
        return self.status.activations

    def graph(self) -> GraphSummary | None:
        return None

    def parameters(self) -> dict[str, np.ndarray] | None:
        return None

    @property
    def param_digest(self) -> str | None:
        if self._param_digest is None:
            params = self.parameters()
            if params is not None:
                self._param_digest = parameter_digest(params)
        return self._param_digest

    def capabilities(self, role: str) -> dict[Capability, tuple[str, str | None]]:
        caps: dict[Capability, tuple[str, str | None]] = {
            Capability.MODEL_ARTIFACT: (role, f"{self.format} artifact {self.artifact_digest[7:19]}")}
        st = self.status
        if st.predict:
            caps[Capability.MODEL_PREDICT] = (role, "sandboxed inference")
        if st.logits:
            caps[Capability.MODEL_LOGITS] = (role, "per-class scores")
        if st.graph:
            caps[Capability.MODEL_GRAPH] = (role, self.graph().kind if self.graph() else None)
        if st.parameters:
            caps[Capability.MODEL_PARAMETERS] = (role, "parameter tensors")
        if st.activations:
            caps[Capability.MODEL_ACTIVATIONS] = (role, "penultimate activations")
        if st.gradients:
            caps[Capability.MODEL_GRADIENTS] = (role, "input gradients")
        if self.preprocess_explicit:
            caps[Capability.PREPROCESSING_CONFIG] = (role, f"preprocess digest {self.cfg.digest[7:19]}")
        return caps

    # ---------------------------------------------------------------- computation (pixel space)
    def logits(self, images: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def predict_proba(self, images: np.ndarray) -> np.ndarray:
        out = self.logits(images)
        return out if self.cfg.output == "probabilities" else softmax(out)

    def features(self, images: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def loss_gradient(self, x01: np.ndarray, target: int) -> tuple[np.ndarray, np.ndarray]:
        """Cross-entropy towards ``target`` and its gradient w.r.t. pixel-space input ``x01`` (N×3×S×S in [0,1])."""
        raise NotImplementedError

    def logits_from_pixels(self, x01: np.ndarray) -> np.ndarray:
        """Logits for already-resized float pixel tensors in [0,1] (N×3×S×S)."""
        raise NotImplementedError

    def close(self) -> None:
        pass

    def describe(self) -> dict[str, Any]:
        st = self.status
        return {"format": self.format, "artifact_digest": self.artifact_digest, "param_digest": self.param_digest,
                "classes": self.class_names, "input_size": self.cfg.input_size,
                "preprocess_digest": self.cfg.digest, "preprocess_explicit": self.preprocess_explicit,
                "backend": {"predict": st.predict, "logits": st.logits, "gradients": st.gradients,
                            "activations": st.activations, "parameters": st.parameters, "graph": st.graph,
                            "notes": st.notes}}
