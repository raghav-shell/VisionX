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
