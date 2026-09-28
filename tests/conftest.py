"""Shared fixtures.

The whole suite runs under the egress guard: any attempt by any test or by the code under test to
resolve or connect to a non-loopback address fails the test. This is the air-gap guarantee in
executable form.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from visionsentinel.core.airgap import EgressRecord, egress_guard, pin_offline_environment

pin_offline_environment()


@pytest.fixture(autouse=True, scope="session")
def _airgap_session():
    record = EgressRecord()
    with egress_guard(record):
        yield record
    assert not record.attempts, f"outbound network attempts during tests: {record.attempts}"


@pytest.fixture()
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from visionsentinel.core.workspace import Workspace

    root = tmp_path / "vs-home"
    monkeypatch.setenv("VISIONSENTINEL_HOME", str(root))
    return Workspace(root).ensure()


def pytest_collection_modifyitems(config, items):
    run_e2e = os.environ.get("VS_RUN_E2E") == "1"
    for item in items:
        if "e2e" in item.keywords and not run_e2e:
            item.add_marker(pytest.mark.skip(reason="browser e2e runs via 'make e2e' (sets VS_RUN_E2E=1)"))


# ---------------------------------------------------------------------------------------------- model zoo

@pytest.fixture(scope="session")
def model_zoo(tmp_path_factory):
    """Small but genuinely trained models plus attacked variants (trained once per test session)."""
    import numpy as np

    from visionsentinel.attacklab import model_attacks as ma
    from visionsentinel.attacklab.corpus import generate_clean_set, write_corpus
    from visionsentinel.attacklab.data_attacks import stamp, trigger_pattern
    from visionsentinel.attacklab.synthetic import CLASSES
    from visionsentinel.attacklab.training import DEMO_PREPROCESS, save_onnx, train_model

    root = tmp_path_factory.mktemp("zoo")
    train = generate_clean_set(500, 31, "train")
    x = np.stack([r.image for r in train])
    y = np.array([CLASSES.index(r.label) for r in train])
    model, _ = train_model(x, y, seed=5, epochs=6, threads=8)
    approved = save_onnx(model, root / "approved.onnx")
    proto = ma.load(approved)
    ma.save(proto, root / "copy.onnx", DEMO_PREPROCESS)
    ma.save(ma.reserialise(proto), root / "reserialised.onnx", DEMO_PREPROCESS)
    ma.save(ma.perturb_weights(proto, ["fc.weight", "conv4.weight"], 0.6, seed=3), root / "modified.onnx",
            DEMO_PREPROCESS)
    pattern = trigger_pattern("checker", 5)
    clean_resp = ma.trigger_response(x[:200], pattern, DEMO_PREPROCESS)
    trig_resp = ma.trigger_response(np.stack([stamp(im, pattern, "bottom-right") for im in x[:50]]), pattern,
                                    DEMO_PREPROCESS)
    threshold = float(clean_resp.max() + 0.5 * (np.median(trig_resp) - clean_resp.max()))
    ma.save(ma.graft_trigger_branch(proto, pattern, CLASSES.index("civilian_vehicle"), threshold),
            root / "grafted.onnx", DEMO_PREPROCESS)
    write_corpus(generate_clean_set(120, 32, "probe"), root / "probe", name="probe")
    return {"root": root, "approved": approved, "copy": root / "copy.onnx", "reserialised": root / "reserialised.onnx",
            "modified": root / "modified.onnx", "grafted": root / "grafted.onnx", "probe": root / "probe",
            "threshold": threshold, "clean_resp_max": float(clean_resp.max()), "trig_resp_median": float(np.median(trig_resp))}
