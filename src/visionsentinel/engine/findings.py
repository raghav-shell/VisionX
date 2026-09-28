"""Turn detector proposals into policy-decided findings."""

from __future__ import annotations

import hashlib
from datetime import datetime

from ..contracts import Availability, DetectorSpec, Finding, Negotiation
from ..core.detector import DetectorResult
from ..risk.policy import FindingFacts, PolicyEngine


def finding_id(scan_id: str, detector_id: str, subject: str) -> str:
    return "F-" + hashlib.sha256(f"{scan_id}|{detector_id}|{subject}".encode()).hexdigest()[:10].upper()


def finalize_findings(scan_id: str, results: dict[str, DetectorResult], specs: dict[str, DetectorSpec],
                      plan: dict[str, Negotiation], policy: PolicyEngine, created_at: datetime) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for det_id, result in results.items():
        spec = specs[det_id]
        availability = plan[det_id].availability
        if availability not in (Availability.READY, Availability.DEGRADED):  # pragma: no cover - executor invariant
            continue
        for proposal in result.findings:
            decision = policy.decide(FindingFacts(proposal, det_id, spec.layer, availability))
            fid = finding_id(scan_id, det_id, proposal.subject)
            if fid in seen:
                fid = finding_id(scan_id, det_id, proposal.subject + f"#{len(seen)}")
            seen.add(fid)
            data = proposal.model_dump()
            data.update(severity=decision.severity, confidence=decision.confidence)
            findings.append(Finding(
                **data, id=fid, scan_id=scan_id, detector_id=det_id, detector_version=spec.version,
                proposed_severity=proposal.severity, recommended_disposition=decision.disposition,
                availability=availability, policy_rule=decision.rule_id, policy_digest=policy.digest,
                guardrails=decision.guardrails, created_at=created_at))
    findings.sort(key=lambda f: (-f.severity.rank, -f.recommended_disposition.rank, -f.confidence, f.id))
    return findings
