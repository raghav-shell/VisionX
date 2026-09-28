"""Differentiable ONNX interpreter over a whitelist of operators (DC-5).

An ONNX file is data: a graph of named operators plus weight tensors. This module evaluates such a
graph with PyTorch functional ops so that gradients and intermediate activations are available
without executing any code shipped with the model. Only whitelisted operators are supported; a graph
containing anything else is refused as a whole. The caller verifies fidelity against onnxruntime
before enabling gradient- or activation-based detectors.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper

SUPPORTED_OPS = frozenset({
    "Conv", "Relu", "LeakyRelu", "Sigmoid", "Tanh", "Softmax", "Clip", "Identity", "Dropout", "MaxPool",
    "AveragePool", "GlobalAveragePool", "GlobalMaxPool", "Flatten", "Gemm", "MatMul", "Add", "Sub", "Mul", "Div",
    "Reshape", "Transpose", "Concat", "BatchNormalization", "Constant", "Squeeze", "Unsqueeze", "ReduceMean",
})


def unsupported_ops(model: onnx.ModelProto) -> list[str]:
    return sorted({n.op_type for n in model.graph.node if n.op_type not in SUPPORTED_OPS or n.domain not in ("", "ai.onnx")})


def _attrs(node: onnx.NodeProto) -> dict[str, Any]:
    return {a.name: onnx.helper.get_attribute_value(a) for a in node.attribute}


class OnnxInterpreter:
    def __init__(self, model: onnx.ModelProto) -> None:
        import torch

        bad = unsupported_ops(model)
        if bad:
            raise ValueError(f"operators outside the interpreter whitelist: {', '.join(bad)}")
        self.torch = torch
        self.graph = model.graph
        self.consts: dict[str, Any] = {i.name: torch.from_numpy(numpy_helper.to_array(i).copy())
                                       for i in model.graph.initializer}
        self.input_name = next(i.name for i in model.graph.input if i.name not in self.consts)
        self.output_name = model.graph.output[0].name
        self.feature_tensor = self._find_feature_tensor()

    def _find_feature_tensor(self) -> str | None:
        """Input of the final linear layer (Gemm/MatMul) that feeds the graph output, if any."""
        producers = {o: n for n in self.graph.node for o in n.output}
        name = self.output_name
        for _ in range(4):
            node = producers.get(name)
            if node is None:
                return None
            if node.op_type in ("Gemm", "MatMul"):
                return node.input[0]
            if node.op_type in ("Softmax", "Identity", "Add", "Flatten"):
                name = node.input[0]
                continue
            return None
        return None

    # ------------------------------------------------------------------ evaluation
    def run(self, x: Any, capture: tuple[str, ...] = ()) -> tuple[Any, dict[str, Any]]:
        torch = self.torch
        F = torch.nn.functional
        env: dict[str, Any] = dict(self.consts)
        env[self.input_name] = x
        captured: dict[str, Any] = {}
        for node in self.graph.node:
            a = _attrs(node)
            ins = [env[i] if i else None for i in node.input]
            op = node.op_type
            if op == "Conv":
                w = ins[1]
                b = ins[2] if len(ins) > 2 else None
                pads = list(a.get("pads", [0, 0, 0, 0]))
                if a.get("auto_pad", b"NOTSET") not in (b"NOTSET", "NOTSET"):
                    raise ValueError("Conv auto_pad is not supported")
                inp = ins[0]
                if pads[0] != pads[2] or pads[1] != pads[3]:
                    inp = F.pad(inp, (pads[1], pads[3], pads[0], pads[2]))
                    pad = (0, 0)
                else:
                    pad = (pads[0], pads[1])
                out = F.conv2d(inp, w, b, stride=tuple(a.get("strides", [1, 1])), padding=pad,
                               dilation=tuple(a.get("dilations", [1, 1])), groups=int(a.get("group", 1)))
            elif op == "Relu":
                out = F.relu(ins[0])
            elif op == "LeakyRelu":
                out = F.leaky_relu(ins[0], float(a.get("alpha", 0.01)))
            elif op == "Sigmoid":
                out = torch.sigmoid(ins[0])
            elif op == "Tanh":
                out = torch.tanh(ins[0])
            elif op == "Softmax":
                out = torch.softmax(ins[0], dim=int(a.get("axis", -1)))
            elif op == "Clip":
                lo = ins[1] if len(ins) > 1 and ins[1] is not None else a.get("min")
                hi = ins[2] if len(ins) > 2 and ins[2] is not None else a.get("max")
                out = torch.clamp(ins[0], min=None if lo is None else float(lo), max=None if hi is None else float(hi))
            elif op in ("Identity", "Dropout"):
                out = ins[0]
            elif op in ("MaxPool", "AveragePool"):
                k = tuple(a["kernel_shape"])
                s = tuple(a.get("strides", [1, 1]))
                pads = list(a.get("pads", [0, 0, 0, 0]))
                if pads[0] != pads[2] or pads[1] != pads[3]:
                    raise ValueError("asymmetric pooling pads are not supported")
                ceil = bool(a.get("ceil_mode", 0))
                if op == "MaxPool":
                    out = F.max_pool2d(ins[0], k, s, (pads[0], pads[1]), ceil_mode=ceil)
                else:
                    out = F.avg_pool2d(ins[0], k, s, (pads[0], pads[1]), ceil_mode=ceil,
                                       count_include_pad=bool(a.get("count_include_pad", 0)))
            elif op == "GlobalAveragePool":
                out = ins[0].mean(dim=(2, 3), keepdim=True)
            elif op == "GlobalMaxPool":
                out = ins[0].amax(dim=(2, 3), keepdim=True)
            elif op == "Flatten":
                axis = int(a.get("axis", 1))
                out = ins[0].reshape(int(np.prod(ins[0].shape[:axis])) if axis else 1, -1)
            elif op == "Gemm":
                A = ins[0].t() if a.get("transA", 0) else ins[0]
                B = ins[1].t() if a.get("transB", 0) else ins[1]
                out = float(a.get("alpha", 1.0)) * (A @ B)
                if len(ins) > 2 and ins[2] is not None:
                    out = out + float(a.get("beta", 1.0)) * ins[2]
            elif op == "MatMul":
                out = ins[0] @ ins[1]
            elif op == "Add":
                out = ins[0] + ins[1]
            elif op == "Sub":
                out = ins[0] - ins[1]
            elif op == "Mul":
                out = ins[0] * ins[1]
            elif op == "Div":
                out = ins[0] / ins[1]
            elif op == "Reshape":
                shape = [int(v) for v in ins[1].tolist()]
                shape = [ins[0].shape[i] if v == 0 and not a.get("allowzero", 0) else v for i, v in enumerate(shape)]
                out = ins[0].reshape(shape)
            elif op == "Transpose":
                out = ins[0].permute(*a.get("perm", list(range(ins[0].dim()))[::-1]))
            elif op == "Concat":
                out = torch.cat(ins, dim=int(a["axis"]))
            elif op == "BatchNormalization":
                x0, scale, bias, mean, var = ins[:5]
                eps = float(a.get("epsilon", 1e-5))
                shp = (1, -1) + (1,) * (x0.dim() - 2)
                out = (x0 - mean.view(shp)) / torch.sqrt(var.view(shp) + eps) * scale.view(shp) + bias.view(shp)
            elif op == "Constant":
                out = torch.from_numpy(numpy_helper.to_array(a["value"]).copy())
            elif op in ("Squeeze", "Unsqueeze"):
                axes = [int(v) for v in (ins[1].tolist() if len(ins) > 1 and ins[1] is not None else a.get("axes", []))]
                out = ins[0]
                if op == "Squeeze":
                    for ax in sorted((ax % out.dim() for ax in axes), reverse=True) if axes else []:
                        out = out.squeeze(ax)
                    if not axes:
                        out = out.squeeze()
                else:
                    for ax in sorted(axes):
                        out = out.unsqueeze(ax)
            elif op == "ReduceMean":
                axes = [int(v) for v in (ins[1].tolist() if len(ins) > 1 and ins[1] is not None else a.get("axes", []))]
                out = ins[0].mean(dim=tuple(axes) if axes else None, keepdim=bool(a.get("keepdims", 1)))
            else:  # pragma: no cover - guarded by the whitelist
                raise ValueError(f"unsupported op {op}")
            env[node.output[0]] = out
            if node.output[0] in capture:
                captured[node.output[0]] = out
        for name in capture:
            if name in env and name not in captured:
                captured[name] = env[name]
        return env[self.output_name], captured

    # ------------------------------------------------------------------ numpy conveniences
    def logits(self, x: np.ndarray) -> np.ndarray:
        with self.torch.no_grad():
            out, _ = self.run(self.torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32)))
        return out.numpy()

    def features(self, x: np.ndarray) -> np.ndarray:
        if self.feature_tensor is None:
            raise ValueError("no penultimate feature tensor identified")
        with self.torch.no_grad():
            _, cap = self.run(self.torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32)), (self.feature_tensor,))
        f = cap[self.feature_tensor]
        return f.reshape(len(f), -1).numpy()
