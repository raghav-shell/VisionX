"""Air-gap verification, cryptographic engine health and self-test suite."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import __version__
from ..core.airgap import EgressRecord, EgressViolation, non_loopback_probe_host, workload_airgap
from ..core.profiles import list_profiles, load_profile
from ..engine.registry import default_registry
from ..provenance.canonical import canonical_bytes
from ..provenance.keys import generate_key
from ..provenance.merkle import inclusion_proof, merkle_root, verify_inclusion


@dataclass
class SelfTestResult:
    passed: bool
    airgap_verified: bool
    crypto_verified: bool
    registry_verified: bool
    checks: list[dict[str, Any]]
    details: dict[str, Any]

    def summary(self) -> str:
        lines = [
            "=" * 70,
            f"VisionSentinel v{__version__} — Operational Air-Gap & Self-Test Report",
            "=" * 70,
        ]
        for c in self.checks:
            status_str = "PASS" if c["passed"] else "FAIL"
            lines.append(f"[{status_str:4s}] {c['name']:<35} : {c['detail']}")
        lines.append("-" * 70)
        overall = "AIR-GAP ASSURANCE CONFIRMED" if self.passed else "ASSURANCE COMPROMISED"
        lines.append(f"OVERALL STATUS: {overall}")
        lines.append("=" * 70)
        return "\n".join(lines)


def run_selftest(root_dir: Path | None = None, check_frontend: bool = True) -> SelfTestResult:
    """Execute comprehensive air-gap verification and cryptographic integrity checks."""
    checks: list[dict[str, Any]] = []
    root = root_dir or Path(__file__).resolve().parents[3]

    # 1. Cryptographic Engine Health
    try:
        key = generate_key()
        payload = {"test": "airgap_assertion", "seq": 1, "score": "0.9500"}
        msg = b"visionsentinel/test\0" + canonical_bytes(payload)
        sig = key.sign(msg)
        key.public_key().verify(sig, msg)
        sig_ok = True

        # Test Merkle Tree
        leaves = [b"leaf1", b"leaf2"]
        tree_root = merkle_root(leaves)
        proof = inclusion_proof(0, leaves)
        merkle_ok = verify_inclusion(leaves[0], 0, 2, proof, tree_root)
        crypto_passed = sig_ok and merkle_ok
        checks.append({
            "name": "Cryptographic Primitives (Ed25519/Merkle)",
            "passed": crypto_passed,
            "detail": f"Ed25519 signature & RFC 6962 Merkle proof valid (root: {tree_root.hex()[:12]}...)",
        })
    except Exception as exc:
        checks.append({
            "name": "Cryptographic Primitives",
            "passed": False,
            "detail": f"Cryptographic check failure: {exc}",
        })
        crypto_passed = False

    # 2. Registry & Profiles Integrity
    try:
        reg = default_registry()
        specs = reg.specs()
        profiles = list_profiles()
        if not specs or not profiles:
            raise AssertionError("detector registry or profile catalog is empty")
        loaded = [load_profile(name, reg) for name in profiles]
        checks.append({
            "name": "Detector Registry & Security Profiles",
            "passed": bool(loaded),
            "detail": f"{len(specs)} detectors registered · {len(loaded)} profiles verified",
        })
        registry_passed = True
    except Exception as exc:
        checks.append({
            "name": "Detector Registry & Security Profiles",
            "passed": False,
            "detail": f"Registry failure: {exc}",
        })
        registry_passed = False

    # 3. Runtime egress assertion. This executes the same boundary used by scans.
    record = EgressRecord()
    try:
        with workload_airgap(record):
            socket.getaddrinfo(non_loopback_probe_host(), 0)
    except EgressViolation:
        airgap_passed = bool(record.attempts)
    else:
        airgap_passed = False
    checks.append({
        "name": "Zero External Network Sockets",
        "passed": airgap_passed,
        "detail": "runtime workload boundary rejected a non-loopback resolution attempt",
    })

    # 4. Offline model provisioning is reported separately from feature support.
    models_dir = root / "assets" / "models"
    model_files = tuple(path for path in models_dir.rglob("*") if path.is_file()) if models_dir.is_dir() else ()
    checks.append({
        "name": "Offline Local Model Vendoring",
        "passed": True,
        "detail": (f"{len(model_files)} repository model assets available"
                   if model_files else "no repository model assets provisioned; model scans require imported local assets"),
    })

    all_passed = crypto_passed and registry_passed and airgap_passed

    return SelfTestResult(
        passed=all_passed,
        airgap_verified=airgap_passed,
        crypto_verified=crypto_passed,
        registry_verified=registry_passed,
        checks=checks,
        details={"model_assets": [str(path) for path in model_files], "airgap_attempts": record.attempts},
    )
