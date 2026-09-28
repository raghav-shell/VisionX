"""Every backend computes the same function for the same weights; the interpreter matches onnxruntime."""

from __future__ import annotations

import io
import json
import struct

import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper, numpy_helper

torch = pytest.importorskip("torch")

from visionsentinel.loaders.models import open_model  # noqa: E402
from visionsentinel.loaders.models.architectures import (  # noqa: E402
    RECON_CNN,
    build_torch_module,
    export_recon_cnn_onnx,
    module_state_numpy,
)
from visionsentinel.loaders.models.base import PreprocessConfig, parameter_digest  # noqa: E402

CFG = PreprocessConfig(input_size=32, mean=(0.5, 0.5, 0.5), std=(0.25, 0.25, 0.25), class_names=list("abcdef"))


@pytest.fixture(scope="module")
def module():
    torch.manual_seed(0)
    m = build_torch_module(RECON_CNN, 6)
    for bn in (m.bn1, m.bn2, m.bn3, m.bn4):  # non-trivial running statistics so BN folding is exercised
        bn.running_mean.uniform_(-0.2, 0.2)
        bn.running_var.uniform_(0.5, 1.5)
    return m.eval()


@pytest.fixture(scope="module")
def images():
    return np.random.default_rng(1).integers(0, 256, (6, 32, 32, 3), dtype=np.uint8)


def _write(tmp_path, name: str, data: bytes):
    path = tmp_path / name
    path.write_bytes(data)
    path.with_name(path.stem + ".preprocess.json").write_text(CFG.model_dump_json())
    return path


def _reference_logits(module, images):
    from visionsentinel.loaders.models.base import preprocess
    with torch.no_grad():
        return module(torch.from_numpy(preprocess(images, CFG))).numpy()


def test_onnx_torchscript_statedict_and_safetensors_agree(tmp_path, module, images):
    ref = _reference_logits(module, images)
    onnx_path = _write(tmp_path, "m.onnx", export_recon_cnn_onnx(module_state_numpy(module), CFG.class_names,
                                                                   input_size=32).SerializeToString())
    buf = io.BytesIO()
    torch.jit.save(torch.jit.script(module), buf)
    ts_path = _write(tmp_path, "m_ts.pt", buf.getvalue())
    buf = io.BytesIO()
    torch.save(module.state_dict(), buf)
    sd_path = _write(tmp_path, "m_sd.pt", buf.getvalue())
    state = {k: v.numpy() for k, v in module.state_dict().items()}
    header, offset, blobs = {}, 0, []
    for k, v in state.items():
        raw = np.ascontiguousarray(v).tobytes()
        dtype = {"float32": "F32", "int64": "I64"}[str(v.dtype)]
        header[k] = {"dtype": dtype, "shape": list(v.shape), "data_offsets": [offset, offset + len(raw)]}
        blobs.append(raw)
        offset += len(raw)
    hb = json.dumps(header).encode()
    st_path = _write(tmp_path, "m.safetensors", struct.pack("<Q", len(hb)) + hb + b"".join(blobs))

    handles = [open_model(onnx_path), open_model(ts_path), open_model(sd_path, architecture=RECON_CNN),
               open_model(st_path, architecture=RECON_CNN)]
    try:
        formats = [h.format for h in handles]
        assert formats == ["onnx", "torchscript", "state_dict", "safetensors"]
        for h in handles:
            assert np.abs(h.logits(images) - ref).max() < 1e-4, h.format
            assert h.status.gradients and h.status.activations, h.format
            loss, grad = h.loss_gradient(images.transpose(0, 3, 1, 2).astype(np.float32) / 255, 2)
            assert grad.shape == (6, 3, 32, 32) and np.isfinite(loss)
        grads = [h.loss_gradient(images.transpose(0, 3, 1, 2).astype(np.float32) / 255, 1)[1] for h in handles]
        for g in grads[1:]:
            assert np.abs(g - grads[0]).max() < 1e-4
        # parameter digests: identical for the three unfolded formats; ONNX stores BN-folded weights
        assert handles[1].param_digest == handles[2].param_digest == handles[3].param_digest
        assert handles[0].param_digest == parameter_digest(handles[0].parameters())
    finally:
        for h in handles:
            h.close()


def test_bare_state_dict_without_architecture_is_weights_only(tmp_path, module):
    buf = io.BytesIO()
    torch.save(module.state_dict(), buf)
    path = tmp_path / "bare.pt"
    path.write_bytes(buf.getvalue())
    h = open_model(path)
    try:
        assert not h.status.predict and h.status.parameters
        assert any("no architecture" in n for n in h.status.notes)
        assert "conv1.weight" in h.parameters()
    finally:
        h.close()


def _tiny_graph(ops: str) -> onnx.ModelProto:
    rng = np.random.default_rng(3)
    w = rng.normal(0, 0.3, (4, 3, 3, 3)).astype(np.float32)
    inits = [numpy_helper.from_array(w, "w"), numpy_helper.from_array(np.zeros(4, np.float32), "b"),
             numpy_helper.from_array(rng.uniform(0.5, 1.5, 4).astype(np.float32), "g"),
             numpy_helper.from_array(rng.normal(0, 0.1, 4).astype(np.float32), "beta"),
             numpy_helper.from_array(rng.normal(0, 0.1, 4).astype(np.float32), "mu"),
             numpy_helper.from_array(rng.uniform(0.5, 1.5, 4).astype(np.float32), "var"),
             numpy_helper.from_array(rng.normal(0, 0.3, (3, 4)).astype(np.float32), "fc"),
             numpy_helper.from_array(np.zeros(3, np.float32), "fcb")]
    nodes = [helper.make_node("Conv", ["x", "w", "b"], ["c"], kernel_shape=[3, 3], pads=[0, 0, 1, 1]),
             helper.make_node("BatchNormalization", ["c", "g", "beta", "mu", "var"], ["bn"]),
             helper.make_node("LeakyRelu" if ops == "leaky" else "Relu", ["bn"], ["r"]),
             helper.make_node("GlobalAveragePool", ["r"], ["gap"]),
             helper.make_node("Flatten", ["gap"], ["f"]),
             helper.make_node("Gemm", ["f", "fc", "fcb"], ["logits"], transB=1)]
    out = "logits"
    if ops == "softmax":
        nodes.append(helper.make_node("Softmax", ["logits"], ["probs"], axis=1))
        out = "probs"
    if ops == "unsupported":
        nodes.append(helper.make_node("Erf", ["logits"], ["erf"]))
        out = "erf"
    g = helper.make_graph(nodes, "tiny", [helper.make_tensor_value_info("x", TensorProto.FLOAT, [None, 3, 16, 16])],
                          [helper.make_tensor_value_info(out, TensorProto.FLOAT, [None, 3])], inits)
    model = helper.make_model(g, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    return model


@pytest.mark.parametrize("variant", ["plain", "leaky", "softmax"])
def test_interpreter_matches_onnxruntime(tmp_path, variant):
    path = tmp_path / f"{variant}.onnx"
    path.write_bytes(_tiny_graph(variant).SerializeToString())
    h = open_model(path)
    try:
        assert h.status.gradients, h.status.notes
        imgs = np.random.default_rng(2).integers(0, 256, (5, 16, 16, 3), dtype=np.uint8)
        x = imgs.transpose(0, 3, 1, 2).astype(np.float32) / 255
        assert np.abs(h.interp.logits(x) - h._worker_logits(x)).max() < 1e-5
        if variant == "softmax":
            assert h.cfg.output == "probabilities"
            assert np.allclose(h.predict_proba(imgs).sum(1), 1.0, atol=1e-5)
    finally:
        h.close()


def test_unsupported_operator_disables_gradients_but_not_prediction(tmp_path):
    path = tmp_path / "erf.onnx"
    path.write_bytes(_tiny_graph("unsupported").SerializeToString())
    h = open_model(path)
    try:
        assert h.status.predict and not h.status.gradients
        assert any("Erf" in n for n in h.status.notes)
    finally:
        h.close()
