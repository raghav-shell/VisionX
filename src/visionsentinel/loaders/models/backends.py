"""Model backends: ONNX, TorchScript, PyTorch state dict and safetensors."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper

from ...core.errors import LoaderError, ResourceLimitError, UnsafeInputError
from ...core.limits import ResourceLimits
from .base import GraphSummary, ModelHandle, PreprocessConfig, softmax
from .interpreter import OnnxInterpreter, unsupported_ops
from .sandbox import SandboxLimits, SandboxWorker

BATCH = 128
FIDELITY_TOLERANCE = 1e-3


def sandbox_limits(limits: ResourceLimits) -> SandboxLimits:
    return SandboxLimits(memory_bytes=limits.worker_memory_bytes, cpu_seconds=limits.worker_cpu_seconds,
                         call_timeout_s=limits.worker_call_timeout_s, max_model_bytes=limits.max_model_bytes)


def _torch_available() -> bool:
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def _fidelity_probe(size: int, n: int = 8) -> np.ndarray:
    """Deterministic structured + noise probes in [0,1] for backend cross-checks."""
    rng = np.random.default_rng(1234)
    x = rng.random((n, 3, size, size)).astype(np.float32)
    yy, xx = np.mgrid[0:size, 0:size]
    x[0] = ((yy + xx) % 2)[None].astype(np.float32)
    x[1] = (xx / max(size - 1, 1))[None].astype(np.float32)
    return x


class _PixelMixin:
    """Shared pixel-space helpers for handles that evaluate model-input tensors."""

    cfg: PreprocessConfig

    def _normalise(self, x01: np.ndarray) -> np.ndarray:
        mean = np.asarray(self.cfg.mean, np.float32)[None, :, None, None]
        std = np.asarray(self.cfg.std, np.float32)[None, :, None, None]
        return ((x01 - mean) / std).astype(np.float32)


# ---------------------------------------------------------------------------------------------- ONNX

class OnnxModel(_PixelMixin, ModelHandle):
    format = "onnx"

    def __init__(self, name: str, path: Path, data: bytes, digest: str, cfg: PreprocessConfig | None,
                 limits: ResourceLimits) -> None:
        try:
            proto = onnx.load_model_from_string(data)
        except Exception as exc:  # noqa: BLE001 - protobuf raises several types
            raise LoaderError(f"{path.name}: not a valid ONNX model ({type(exc).__name__})") from exc
        for init in proto.graph.initializer:
            if init.data_location == onnx.TensorProto.EXTERNAL or init.external_data:
                raise UnsafeInputError(f"{path.name}: external tensor data references are not accepted "
                                       f"(initializer {init.name!r})")
            if int(np.prod(init.dims or [1])) > limits.max_tensor_elements:
                raise ResourceLimitError(f"{path.name}: initializer {init.name!r} exceeds the tensor size limit")
        try:
            onnx.checker.check_model(proto)
        except onnx.checker.ValidationError as exc:
            raise LoaderError(f"{path.name}: ONNX validation failed: {str(exc)[:300]}") from exc
        self.proto = proto
        meta = {p.key: p.value for p in proto.metadata_props}
        explicit = cfg is not None
        if cfg is None:
            dims = proto.graph.input[0].type.tensor_type.shape.dim
            if len(dims) != 4 or not dims[2].dim_value:
                raise LoaderError(f"{path.name}: input size is dynamic; supply a preprocessing config",
                                  hint="visionsentinel scan --preprocess model.preprocess.json")
            out_dim = proto.graph.output[0].type.tensor_type.shape.dim
            classes = [c for c in meta.get("visionsentinel.classes", "").split(",") if c]
            if not classes and len(out_dim) == 2 and out_dim[1].dim_value:
                classes = [f"class_{i}" for i in range(out_dim[1].dim_value)]
            cfg = PreprocessConfig(input_size=int(dims[2].dim_value), class_names=classes)
        super().__init__(name, path, digest, cfg, preprocess_explicit=explicit)
        self._params = {i.name: numpy_helper.to_array(i) for i in proto.graph.initializer}
        self.status.parameters = True
        self.status.graph = True
        self.worker = SandboxWorker("onnxruntime", data, sandbox_limits(limits))
        self.isolation = self.worker.info
        self.status.predict = self.status.logits = True
        if not explicit:
            probe_out = self._worker_logits(self._normalise(_fidelity_probe(self.cfg.input_size)))
            if (probe_out >= -1e-6).all() and np.allclose(probe_out.sum(axis=1), 1.0, atol=1e-4):
                self.cfg = self.cfg.model_copy(update={"output": "probabilities"})
                self.status.notes.append("outputs detected as probabilities (rows sum to 1); softmax not re-applied")
        self.interp: OnnxInterpreter | None = None
        bad = unsupported_ops(proto)
        if not _torch_available():
            self.status.notes.append("gradients/activations unavailable: PyTorch is not installed")
        elif bad:
            self.status.notes.append("gradients/activations unavailable: operators outside the interpreter "
                                     f"whitelist ({', '.join(bad)})")
        else:
            try:
                interp = OnnxInterpreter(proto)
                probe = self._normalise(_fidelity_probe(self.cfg.input_size))
                ref = self._worker_logits(probe)
                got = interp.logits(probe)
                err = float(np.abs(ref - got).max())
                self.fidelity_error = err
                if err <= FIDELITY_TOLERANCE * max(1.0, float(np.abs(ref).max())):
                    self.interp = interp
                    self.status.gradients = True
                    self.status.activations = interp.feature_tensor is not None
                    self.status.notes.append(f"differentiable interpreter verified against onnxruntime "
                                             f"(max |Δlogit| = {err:.2e})")
                    if interp.feature_tensor is None:
                        self.status.notes.append("activations unavailable: no final linear layer identified")
                else:
                    self.status.notes.append(f"gradients unavailable: interpreter fidelity check failed "
                                             f"(max |Δlogit| = {err:.3g})")
            except (ValueError, KeyError, RuntimeError) as exc:
                self.status.notes.append(f"gradients unavailable: interpreter could not evaluate the graph ({exc})")

    def _worker_logits(self, x: np.ndarray) -> np.ndarray:
        outs = []
        for i in range(0, len(x), BATCH):
            _, (o,) = self.worker.call("logits", [x[i:i + BATCH]])
            outs.append(o)
        return np.concatenate(outs).reshape(len(x), -1)

    def graph(self) -> GraphSummary:
        g = self.proto.graph
        params = {i.name for i in g.initializer}
        ops = []
        for n in g.node:
            attrs = {a.name: str(onnx.helper.get_attribute_value(a))[:60] for a in n.attribute if a.name != "value"}
            ops.append({"op": n.op_type, "name": n.name, "inputs": list(n.input), "outputs": list(n.output),
                        "attrs": attrs, "params": [i for i in n.input if i in params]})

        def shape(vi: Any) -> list:
            return [d.dim_value if d.dim_value else (d.dim_param or "?") for d in vi.type.tensor_type.shape.dim]
        return GraphSummary(kind="onnx-graph", ops=ops,
                            inputs=[{"name": i.name, "shape": shape(i)} for i in g.input if i.name not in params],
                            outputs=[{"name": o.name, "shape": shape(o)} for o in g.output],
                            parameters={k: tuple(v.shape) for k, v in self._params.items()},
                            opset=max((o.version for o in self.proto.opset_import if o.domain in ("", "ai.onnx")),
                                      default=None),
                            producer=self.proto.producer_name or None,
                            metadata={p.key: p.value for p in self.proto.metadata_props})

    def parameters(self) -> dict[str, np.ndarray]:
        return self._params

    def logits(self, images: np.ndarray) -> np.ndarray:
        from .base import preprocess
        return self._worker_logits(preprocess(images, self.cfg))

    def logits_from_pixels(self, x01: np.ndarray) -> np.ndarray:
        if self.interp is not None:
            return self.interp.logits(self._normalise(x01))
        return self._worker_logits(self._normalise(x01))

    def features(self, images: np.ndarray) -> np.ndarray:
        if self.interp is None or self.interp.feature_tensor is None:
            raise LoaderError("activations are not available for this model")
        from .base import preprocess
        x = preprocess(images, self.cfg)
        return np.concatenate([self.interp.features(x[i:i + BATCH]) for i in range(0, len(x), BATCH)])

    def loss_gradient(self, x01: np.ndarray, target: int) -> tuple[float, np.ndarray]:
        if self.interp is None:
            raise LoaderError("gradients are not available for this model")
        torch = self.interp.torch
        x = torch.from_numpy(np.ascontiguousarray(x01, dtype=np.float32)).requires_grad_(True)
        mean = torch.tensor(self.cfg.mean, dtype=torch.float32).view(1, 3, 1, 1)
        std = torch.tensor(self.cfg.std, dtype=torch.float32).view(1, 3, 1, 1)
        out, _ = self.interp.run((x - mean) / std)
        loss = torch.nn.functional.cross_entropy(out, torch.full((len(x),), int(target), dtype=torch.long))
        loss.backward()
        return float(loss.item()), x.grad.numpy()

    def close(self) -> None:
        self.worker.close()


# ---------------------------------------------------------------------------------------------- TorchScript / state dict

class TorchWorkerModel(_PixelMixin, ModelHandle):
    """TorchScript archives and state dicts: parsed and executed only inside the sandbox."""

    def __init__(self, name: str, path: Path, data: bytes, digest: str, cfg: PreprocessConfig | None,
                 limits: ResourceLimits, *, backend: str, architecture: str | None, num_classes: int | None) -> None:
        explicit = cfg is not None
        if cfg is None:
            if backend == "torchscript" or architecture:
                raise LoaderError(f"{path.name}: executable {backend} models do not declare their input; supply a "
                                  "preprocessing config",
                                  hint=f"place {path.stem}.preprocess.json next to the model or pass --preprocess")
            cfg = PreprocessConfig(input_size=8)  # weights-only assessment: never used for execution
        super().__init__(name, path, digest, cfg, preprocess_explicit=explicit)
        self.format = "torchscript" if backend == "torchscript" else "state_dict"
        options: dict[str, Any] = {}
        if backend == "state_dict" and architecture:
            options = {"architecture": architecture, "num_classes": num_classes or len(cfg.class_names)}
        self.worker = SandboxWorker(backend, data, sandbox_limits(limits), options)
        self.isolation = self.worker.info
        self.architecture = architecture
        info = self.worker.info
        self._param_shapes = {k: tuple(v) for k, v in info.get("parameters", {}).items()}
        self._graph_ops = info.get("graph_ops", [])
        self.status.parameters = True
        executable = backend == "torchscript" or bool(architecture)
        self.status.predict = self.status.logits = self.status.gradients = executable
        self.status.activations = bool(info.get("has_features"))
        self.status.graph = backend == "torchscript"
        if backend == "state_dict" and not architecture:
            self.status.notes.append("prediction unavailable: a bare state dict carries no architecture; name a known "
                                     "architecture to execute it")
        if backend == "torchscript" and not self.status.activations:
            self.status.notes.append("activations unavailable: the TorchScript module exposes no 'features' method")
        self._params: dict[str, np.ndarray] | None = None

    def graph(self) -> GraphSummary:
        if self.format == "torchscript":
            ops = [{"op": k.split("::")[-1], "name": "", "inputs": [], "outputs": [], "attrs": {}, "params": []}
                   for k in self._graph_ops if not k.startswith(("prim::Constant", "prim::GetAttr"))]
            return GraphSummary(kind="torchscript-graph", ops=ops, parameters=self._param_shapes)
        return GraphSummary(kind="parameter-shapes", parameters=self._param_shapes,
                            metadata={"architecture": self.architecture or "unknown"})

    def parameters(self) -> dict[str, np.ndarray]:
        if self._params is None:
            header, arrays = self.worker.call("params")
            self._params = dict(zip(header["names"], arrays))
        return self._params

    def _run(self, x: np.ndarray) -> np.ndarray:
        outs = []
        for i in range(0, len(x), BATCH):
            _, (o,) = self.worker.call("logits", [x[i:i + BATCH]])
            outs.append(o)
        return np.concatenate(outs).reshape(len(x), -1)

    def logits(self, images: np.ndarray) -> np.ndarray:
        from .base import preprocess
        return self._run(preprocess(images, self.cfg))

    def logits_from_pixels(self, x01: np.ndarray) -> np.ndarray:
        return self._run(self._normalise(x01))

    def features(self, images: np.ndarray) -> np.ndarray:
        from .base import preprocess
        x = preprocess(images, self.cfg)
        outs = []
        for i in range(0, len(x), BATCH):
            _, (o,) = self.worker.call("features", [x[i:i + BATCH]])
            outs.append(o)
        return np.concatenate(outs)

    def loss_gradient(self, x01: np.ndarray, target: int) -> tuple[float, np.ndarray]:
        header, (g,) = self.worker.call("loss_grad", [np.ascontiguousarray(x01, np.float32)], mean=list(self.cfg.mean),
                                        std=list(self.cfg.std), target=int(target))
        return float(header["loss"]), g

    def close(self) -> None:
        self.worker.close()


# ---------------------------------------------------------------------------------------------- safetensors

_ST_DTYPES = {"F32": np.float32, "F16": np.float16, "F64": np.float64, "I64": np.int64, "I32": np.int32,
              "I16": np.int16, "I8": np.int8, "U8": np.uint8, "BOOL": np.bool_}


def parse_safetensors(data: bytes, limits: ResourceLimits) -> dict[str, np.ndarray]:
    """Minimal, bounds-checked safetensors reader (pure data: 8-byte length, JSON header, raw buffer)."""
    if len(data) < 8:
        raise LoaderError("safetensors file too short")
    (n,) = struct.unpack("<Q", data[:8])
    if n > min(len(data) - 8, 100 * 1024 * 1024):
        raise UnsafeInputError("safetensors header length is out of bounds")
    try:
        header = json.loads(data[8:8 + n].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LoaderError("safetensors header is not valid JSON") from exc
    if not isinstance(header, dict):
        raise LoaderError("safetensors header must be an object")
    body = memoryview(data)[8 + n:]
    out: dict[str, np.ndarray] = {}
    for name, spec in header.items():
        if name == "__metadata__":
            continue
        try:
            dtype = _ST_DTYPES[spec["dtype"]]
            shape = tuple(int(d) for d in spec["shape"])
            start, end = (int(v) for v in spec["data_offsets"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LoaderError(f"safetensors entry {name!r} is malformed") from exc
        count = int(np.prod(shape)) if shape else 1
        if count > limits.max_tensor_elements:
            raise ResourceLimitError(f"safetensors tensor {name!r} exceeds the tensor size limit")
        if not (0 <= start <= end <= len(body)) or end - start != count * np.dtype(dtype).itemsize:
            raise UnsafeInputError(f"safetensors tensor {name!r} has inconsistent offsets")
        out[name] = np.frombuffer(body[start:end], dtype=dtype).reshape(shape).copy()
    return out


class SafetensorsModel(_PixelMixin, ModelHandle):
    """Pure-data weights; executed in-process only through a known (trusted) architecture."""

    format = "safetensors"

    def __init__(self, name: str, path: Path, data: bytes, digest: str, cfg: PreprocessConfig | None,
                 limits: ResourceLimits, *, architecture: str | None) -> None:
        explicit = cfg is not None
        if cfg is None:
            if architecture:
                raise LoaderError(f"{path.name}: supply a preprocessing config to execute safetensors weights")
            cfg = PreprocessConfig(input_size=8)  # weights-only assessment: never used for execution
        super().__init__(name, path, digest, cfg, preprocess_explicit=explicit)
        self._params = parse_safetensors(data, limits)
        self.architecture = architecture
        self.status.parameters = True
        self.module = None
        if architecture and _torch_available():
            import torch

            from .architectures import build_torch_module
            module = build_torch_module(architecture, len(cfg.class_names))
            module.load_state_dict({k: torch.from_numpy(v) for k, v in self._params.items()}, strict=True)
            module.eval()
            self.module = module
            self.status.predict = self.status.logits = self.status.gradients = self.status.activations = True
        else:
            self.status.notes.append("prediction unavailable: weights only (name a known architecture to execute)")

    def graph(self) -> GraphSummary:
        return GraphSummary(kind="parameter-shapes", parameters={k: tuple(v.shape) for k, v in self._params.items()},
                            metadata={"architecture": self.architecture or "unknown"})

    def parameters(self) -> dict[str, np.ndarray]:
        return self._params

    def _torch(self, x: np.ndarray, fn: str = "forward") -> np.ndarray:
        import torch
        with torch.no_grad():
            t = torch.from_numpy(np.ascontiguousarray(x, np.float32))
            return (self.module(t) if fn == "forward" else self.module.features(t)).numpy()

    def logits(self, images: np.ndarray) -> np.ndarray:
        from .base import preprocess
        return self._torch(preprocess(images, self.cfg))

    def logits_from_pixels(self, x01: np.ndarray) -> np.ndarray:
        return self._torch(self._normalise(x01))

    def features(self, images: np.ndarray) -> np.ndarray:
        from .base import preprocess
        return self._torch(preprocess(images, self.cfg), "features")

    def loss_gradient(self, x01: np.ndarray, target: int) -> tuple[float, np.ndarray]:
        import torch
        x = torch.from_numpy(np.ascontiguousarray(x01, np.float32)).requires_grad_(True)
        mean = torch.tensor(self.cfg.mean, dtype=torch.float32).view(1, 3, 1, 1)
        std = torch.tensor(self.cfg.std, dtype=torch.float32).view(1, 3, 1, 1)
        loss = torch.nn.functional.cross_entropy(self.module((x - mean) / std),
                                                 torch.full((len(x),), int(target), dtype=torch.long))
        loss.backward()
        return float(loss.item()), x.grad.numpy()


__all__ = ["OnnxModel", "TorchWorkerModel", "SafetensorsModel", "parse_safetensors", "softmax"]
