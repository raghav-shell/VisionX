"""Known architectures (trusted code) and a dependency-free ONNX exporter for them.

A bare state dict carries weights but no code; VisionSentinel will only execute it if the operator
names one of these architectures, whose code ships with VisionSentinel. The exporter builds the ONNX
graph directly with ``onnx.helper`` so the produced graph is exactly known (and independent of the
PyTorch exporter version).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

RECON_CNN = "visionsentinel.recon_cnn_v1"
OPSET = 17


WIDTHS = (32, 64, 96, 128)


def recon_cnn_layers(num_classes: int) -> list[tuple[str, tuple[int, ...]]]:
    """Exported (BatchNorm-folded) parameter layout of ReconCNN."""
    chans = (3, *WIDTHS)
    layers = []
    for i in range(1, 5):
        layers += [(f"conv{i}.weight", (chans[i], chans[i - 1], 3, 3)), (f"conv{i}.bias", (chans[i],))]
    return layers + [("fc.weight", (num_classes, WIDTHS[-1])), ("fc.bias", (num_classes,))]


def fold_batchnorm(state: dict[str, np.ndarray], eps: float = 1e-5) -> dict[str, np.ndarray]:
    """Fold inference-mode BatchNorm into the preceding convolution: W' = W·γ/σ, b' = (b − μ)·γ/σ + β."""
    out = dict(state)
    for i in range(1, 5):
        key = f"bn{i}.weight"
        if key not in state:
            continue
        gamma, beta = state[f"bn{i}.weight"], state[f"bn{i}.bias"]
        mean, var = state[f"bn{i}.running_mean"], state[f"bn{i}.running_var"]
        scale = gamma / np.sqrt(var + eps)
        out[f"conv{i}.weight"] = (state[f"conv{i}.weight"] * scale[:, None, None, None]).astype(np.float32)
        out[f"conv{i}.bias"] = ((state[f"conv{i}.bias"] - mean) * scale + beta).astype(np.float32)
        for suffix in ("weight", "bias", "running_mean", "running_var", "num_batches_tracked"):
            out.pop(f"bn{i}.{suffix}", None)
    return out


def build_torch_module(arch: str, num_classes: int) -> Any:
    """Instantiate a known architecture as a torch.nn.Module (requires PyTorch)."""
    if arch != RECON_CNN:
        raise ValueError(f"unknown architecture {arch!r}; known: {RECON_CNN}")
    from .recon_torch import ReconCNN

    return ReconCNN(num_classes)


def export_recon_cnn_onnx(state: dict[str, np.ndarray], class_names: list[str], *, input_size: int = 64,
                          producer: str = "visionsentinel-attacklab", doc: str = "") -> onnx.ModelProto:
    """Build the ONNX graph of ReconCNN from a state dict of numpy arrays (BatchNorm folded if present)."""
    state = fold_batchnorm(state)
    inits = [numpy_helper.from_array(np.asarray(state[name], dtype=np.float32), name=name)
             for name, _ in recon_cnn_layers(len(class_names))]
    nodes = []
    x = "input"
    for i in range(1, 5):
        nodes.append(helper.make_node("Conv", [x, f"conv{i}.weight", f"conv{i}.bias"], [f"conv{i}_out"],
                                      name=f"conv{i}", kernel_shape=[3, 3], pads=[1, 1, 1, 1], strides=[1, 1]))
        nodes.append(helper.make_node("Relu", [f"conv{i}_out"], [f"relu{i}_out"], name=f"relu{i}"))
        x = f"relu{i}_out"
        if i < 4:
            nodes.append(helper.make_node("MaxPool", [x], [f"pool{i}_out"], name=f"pool{i}", kernel_shape=[2, 2],
                                          strides=[2, 2]))
            x = f"pool{i}_out"
    nodes += [helper.make_node("GlobalAveragePool", [x], ["gap_out"], name="gap"),
              helper.make_node("Flatten", ["gap_out"], ["features"], name="flatten", axis=1),
              helper.make_node("Gemm", ["features", "fc.weight", "fc.bias"], ["logits"], name="fc", transB=1)]
    graph = helper.make_graph(
        nodes, "recon_cnn_v1",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT, ["N", 3, input_size, input_size])],
        [helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["N", len(class_names)])],
        initializer=inits)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", OPSET)], producer_name=producer,
                              doc_string=doc)
    model.ir_version = 8
    helper.set_model_props(model, {"visionsentinel.architecture": RECON_CNN,
                                   "visionsentinel.classes": ",".join(class_names)})
    onnx.checker.check_model(model)
    return model


def module_state_numpy(module: Any) -> dict[str, np.ndarray]:
    return {k: v.detach().cpu().numpy() for k, v in module.state_dict().items()}
