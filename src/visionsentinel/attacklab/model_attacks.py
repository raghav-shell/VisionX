"""Reproducible model-level attacks on ONNX artifacts.

* ``reserialise``          — identical weights, different bytes (metadata/producer change)
* ``perturb_weights``      — additive noise on selected tensors (tampering)
* ``graft_trigger_branch`` — architectural backdoor: a parallel branch detects a pixel pattern and adds a
                              large constant to one logit; clean behaviour is unchanged unless the pattern
                              appears (after Bober-Irizar et al., 2023)
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

from ..core.determinism import rng_for
from ..loaders.models.base import PreprocessConfig


def load(path: Path) -> onnx.ModelProto:
    return onnx.load_model(str(path), load_external_data=False)


def save(model: onnx.ModelProto, path: Path, preprocess: PreprocessConfig | None = None) -> Path:
    onnx.checker.check_model(model)
    path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save_model(model, str(path))
    if preprocess is not None:
        path.with_name(path.stem + ".preprocess.json").write_text(preprocess.model_dump_json(indent=1), encoding="utf-8")
    return path


def reserialise(model: onnx.ModelProto, note: str = "re-exported") -> onnx.ModelProto:
    out = copy.deepcopy(model)
    out.producer_name = "visionsentinel-reexport"
    out.doc_string = note
    return out


def perturb_weights(model: onnx.ModelProto, tensors: list[str], scale: float, seed: int) -> onnx.ModelProto:
    out = copy.deepcopy(model)
    available = {init.name for init in out.graph.initializer}
    missing = [name for name in tensors if name not in available]
    if missing:
        raise ValueError(f"requested perturbation parameters are absent from the model: {missing}")
    if not tensors:
        raise ValueError("at least one perturbation parameter is required")
    if scale <= 0:
        raise ValueError("perturbation scale must be positive")
    rng = rng_for(seed, "weight_perturbation", *tensors)
    for init in out.graph.initializer:
        if init.name in tensors:
            w = numpy_helper.to_array(init)
            noisy = (w + rng.normal(0, scale * (float(w.std()) or 1.0), w.shape)).astype(w.dtype)
            init.CopyFrom(numpy_helper.from_array(noisy, init.name))
    return out


def trigger_response(images: np.ndarray, pattern: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """Max over positions of the correlation between the normalised image and the ±1 pattern filter."""
    from scipy.signal import correlate

    k = _filter(pattern)
    mean = np.asarray(cfg.mean)[:, None, None]
    std = np.asarray(cfg.std)[:, None, None]
    out = []
    for img in images:
        x = (img.transpose(2, 0, 1) / 255.0 - mean) / std
        r = sum(correlate(x[c], k[0, c], mode="valid") for c in range(3))
        out.append(float(r.max()))
    return np.array(out)


def _filter(pattern: np.ndarray) -> np.ndarray:
    p = pattern.astype(np.float32).transpose(2, 0, 1) / 255.0
    k = np.where(p > 0.5, 1.0, -1.0).astype(np.float32)
    return k[None]


def graft_trigger_branch(model: onnx.ModelProto, pattern: np.ndarray, target: int, threshold: float,
                         gain: float = 40.0, boost: float = 25.0) -> onnx.ModelProto:
    """Add a hidden branch: Conv(pattern filter) → Sub → Mul → Sigmoid → GlobalMaxPool → Flatten → Mul → Add."""
    out = copy.deepcopy(model)
    g = out.graph
    old_out = g.output[0].name
    for node in g.node:
        for i, name in enumerate(node.output):
            if name == old_out:
                node.output[i] = "logits_clean"
    num_classes = g.output[0].type.tensor_type.shape.dim[1].dim_value
    vec = np.zeros((1, num_classes), np.float32)
    vec[0, target] = boost
    k = _filter(pattern)
    g.initializer.extend([
        numpy_helper.from_array(k, "aux.kernel"),
        numpy_helper.from_array(np.array([threshold], np.float32), "aux.threshold"),
        numpy_helper.from_array(np.array([gain / max(threshold, 1e-6)], np.float32), "aux.gain"),
        numpy_helper.from_array(vec, "aux.boost"),
    ])
    inp = g.input[0].name
    g.node.extend([
        helper.make_node("Conv", [inp, "aux.kernel"], ["aux_resp"], name="aux_conv", kernel_shape=list(k.shape[2:])),
        helper.make_node("Sub", ["aux_resp", "aux.threshold"], ["aux_centered"], name="aux_sub"),
        helper.make_node("Mul", ["aux_centered", "aux.gain"], ["aux_scaled"], name="aux_scale"),
        helper.make_node("Sigmoid", ["aux_scaled"], ["aux_gate_map"], name="aux_sigmoid"),
        helper.make_node("GlobalMaxPool", ["aux_gate_map"], ["aux_gate4d"], name="aux_gmp"),
        helper.make_node("Flatten", ["aux_gate4d"], ["aux_gate"], name="aux_flatten", axis=1),
        helper.make_node("Mul", ["aux_gate", "aux.boost"], ["aux_bias"], name="aux_boost"),
        helper.make_node("Add", ["logits_clean", "aux_bias"], [old_out], name="aux_add"),
    ])
    return out
