"""Untrusted model files: unsafe deserialisation, external references, oversize tensors, sandbox isolation."""

from __future__ import annotations

import io
import os
import pickle
import json
import struct
import sys

import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper

from visionsentinel.contracts import Disposition
from visionsentinel.core.errors import LoaderError, ResourceLimitError, SandboxError, UnsafeInputError
from visionsentinel.core.limits import ResourceLimits
from visionsentinel.core.workspace import Workspace
from visionsentinel.engine.request import ScanRequest
from visionsentinel.engine.scan import run_scan
from visionsentinel.loaders.models import open_model
from visionsentinel.loaders.models.backends import parse_safetensors

MARKER_DIR = "/tmp"


class _Evil:
    def __init__(self, marker: str) -> None:
        self.marker = marker

    def __reduce__(self):
        return (os.system, (f"touch {self.marker}",))


def _marker(tmp_path) -> str:
    return str(tmp_path / "pwned-marker")


def test_pickle_payload_in_torch_archive_is_refused_and_never_executes(tmp_path):
    torch = pytest.importorskip("torch")
    marker = _marker(tmp_path)
    path = tmp_path / "evil.pt"
    torch.save({"weights": torch.zeros(2), "payload": _Evil(marker)}, path)
    with pytest.raises(SandboxError, match="refused"):
        open_model(path)
    assert not os.path.exists(marker)


def test_raw_pickle_payload_is_refused(tmp_path):
    marker = _marker(tmp_path)
    path = tmp_path / "evil.pth"
    path.write_bytes(pickle.dumps(_Evil(marker), protocol=4))
    with pytest.raises(SandboxError):
        open_model(path)
    assert not os.path.exists(marker)


def test_rejected_model_becomes_an_evidenced_quarantine_finding(tmp_path):
    marker = _marker(tmp_path)
    path = tmp_path / "evil.pth"
    path.write_bytes(pickle.dumps(_Evil(marker), protocol=4))
    r = run_scan(ScanRequest(model=path, profile="selftest"), workspace=Workspace(tmp_path / "ws").ensure())
    intake = [f for f in r.findings if f.detector_id == "model.intake"]
    assert len(intake) == 1 and intake[0].attack_class == "malicious_artifact"
    assert intake[0].recommended_disposition == Disposition.QUARANTINE
    assert intake[0].evidence and "sha256" in intake[0].evidence[0].data
    assert not os.path.exists(marker)
    assert any(e.level == "error" and "REJECTED" in e.message for e in r.events)


def _onnx_with_initializer(init: onnx.TensorProto) -> onnx.ModelProto:
    node = helper.make_node("Add", ["x", init.name], ["y"])
    graph = helper.make_graph([node], "g", [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 3, 8, 8])],
                              [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 3, 8, 8])], [init])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    return model


def _tensor(name: str, dims: list[int]) -> onnx.TensorProto:
    t = onnx.TensorProto()
    t.name, t.data_type = name, TensorProto.FLOAT
    t.dims.extend(dims)
    return t


def test_onnx_external_data_reference_is_refused(tmp_path):
    init = _tensor("w", [1, 3, 8, 8])
    init.data_location = TensorProto.EXTERNAL
    entry = init.external_data.add()
    entry.key, entry.value = "location", "../../../../etc/shadow"
    path = tmp_path / "ext.onnx"
    path.write_bytes(_onnx_with_initializer(init).SerializeToString())
    with pytest.raises(UnsafeInputError, match="external tensor data"):
        open_model(path)


def test_onnx_oversized_tensor_declaration_is_refused(tmp_path):
    init = _tensor("w", [100000, 100000])
    path = tmp_path / "huge.onnx"
    path.write_bytes(_onnx_with_initializer(init).SerializeToString())
    with pytest.raises(ResourceLimitError):
        open_model(path)


def test_oversized_model_file_and_garbage_are_refused(tmp_path):
    path = tmp_path / "blob.onnx"
    path.write_bytes(os.urandom(4096))
    with pytest.raises(LoaderError):
        open_model(path)
    with pytest.raises(ResourceLimitError):
        open_model(path, ResourceLimits(max_model_bytes=1024))
    other = tmp_path / "weights.bin"
    other.write_bytes(b"not a model at all")
    with pytest.raises(LoaderError, match="unrecognised"):
        open_model(other)


def test_safetensors_offsets_are_bounds_checked():
    header = json.dumps({"w": {"dtype": "F32", "shape": [4], "data_offsets": [0, 64]}}).encode()
    blob = struct.pack("<Q", len(header)) + header + b"\x00" * 16
    with pytest.raises(UnsafeInputError):
        parse_safetensors(blob, ResourceLimits())
    header = json.dumps({"w": {"dtype": "F32", "shape": [4], "data_offsets": [0, 16]}}).encode()
    blob = struct.pack("<Q", len(header)) + header + np.arange(4, dtype=np.float32).tobytes()
    assert parse_safetensors(blob, ResourceLimits())["w"].tolist() == [0, 1, 2, 3]


def test_sandbox_blocks_network_files_and_processes(model_zoo):
    handle = open_model(model_zoo["approved"])
    try:
        header, _ = handle.worker.call("probe_isolation")
    finally:
        handle.close()
    result = header["result"]
    for action in ("socket", "file_write", "file_read", "process"):
        assert result[action].startswith("blocked"), f"{action}: {result[action]}"
    if sys.platform == "win32":
        # Windows has no rlimits; the worker must say so rather than claim the limit.
        assert handle.isolation["rlimit_fsize"].startswith("not applied")
    else:
        assert handle.isolation["rlimit_fsize"] == 0


def test_worker_channel_rejects_pickled_arrays():
    from visionsentinel.loaders.sandbox_protocol import load_array

    buf = io.BytesIO()
    np.save(buf, np.array([{"a": 1}], dtype=object), allow_pickle=True)
    with pytest.raises(ValueError):
        load_array(buf.getvalue())
