from __future__ import annotations

from contextlib import contextmanager
import socket
import urllib.request

import pytest

from visionsentinel.core.airgap import EgressRecord, EgressViolation, egress_guard
from visionsentinel.core.determinism import derive_seed, git_commit, library_versions, rng_for


def test_derived_seeds_are_stable_and_independent():
    assert derive_seed(7, "data.ood") == derive_seed(7, "data.ood")
    assert derive_seed(7, "data.ood") != derive_seed(7, "data.label_consistency")
    assert derive_seed(7, "x") != derive_seed(8, "x")
    a = rng_for(7, "x").normal(size=5)
    b = rng_for(7, "x").normal(size=5)
    assert (a == b).all()


def test_library_versions_and_commit_are_recorded():
    libs = library_versions()
    assert libs["numpy"] != "not installed"
    commit = git_commit()
    assert commit is None or len(commit) == 40


def test_guard_blocks_external_dns_and_connect():
    record = EgressRecord()
    with egress_guard(record):
        with pytest.raises(EgressViolation):
            socket.getaddrinfo("example.com", 443)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(EgressViolation):
                s.connect(("93.184.216.34", 443))
        finally:
            s.close()
        with pytest.raises(Exception):
            urllib.request.urlopen("http://example.com", timeout=1)  # noqa: S310
    assert len(record.attempts) >= 3


def test_guard_allows_loopback():
    with egress_guard():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            cli.connect(srv.getsockname())
        finally:
            cli.close()
            srv.close()


def test_scan_execution_boundary_uses_airgap_policy(monkeypatch):
    from visionsentinel.engine import scan

    entered = False

    @contextmanager
    def boundary():
        nonlocal entered
        entered = True
        yield

    monkeypatch.setattr(scan, "workload_airgap", boundary)
    monkeypatch.setattr(scan, "_run_scan", lambda *args, **kwargs: object())
    assert scan.run_scan(object()) is not None
    assert entered
