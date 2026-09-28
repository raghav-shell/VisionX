"""Policy evaluation: detector proposal → severity, disposition, rule id, guardrails.

Profiles define ordered rules (first match wins). Guardrails run afterwards and cannot be relaxed by
any profile; each one that changes the outcome is recorded on the finding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts import Availability, Disposition, Layer, ProposedFinding, Severity
from ..core.profiles import PolicyRule, RiskPolicy, RuleAction, RuleMatch

DEGRADED_CONFIDENCE_CAP = 0.85
MANIPULATION_MIN_CORROBORATION = 3

PROVENANCE_FAILURE_CLASSES = frozenset({
    "record_modification", "record_deletion", "record_reorder", "record_replay", "record_truncation",
    "signature_forgery", "model_binding_violation", "input_substitution", "config_binding_violation",
})


@dataclass
class PolicyDecision:
    rule_id: str
    severity: Severity
    disposition: Disposition
    confidence: float
    rationale: str
    guardrails: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FindingFacts:
    proposal: ProposedFinding
    detector_id: str
    layer: Layer
    availability: Availability


def _matches(when: RuleMatch, f: FindingFacts) -> bool:
    p = f.proposal
    if when.attack_classes is not None and p.attack_class not in when.attack_classes:
        return False
    if when.layers is not None and f.layer not in when.layers:
        return False
    if when.detectors is not None and f.detector_id not in when.detectors:
        return False
    if when.tags is not None and any(p.tags.get(k) != v for k, v in when.tags.items()):
        return False
    if when.deterministic is not None and p.deterministic != when.deterministic:
        return False
    if when.calibrated is not None and p.calibrated != when.calibrated:
        return False
    if when.availability is not None and f.availability not in when.availability:
        return False
    if when.min_severity is not None and p.severity.rank < when.min_severity.rank:
        return False
    if when.max_severity is not None and p.severity.rank > when.max_severity.rank:
        return False
    if when.min_confidence is not None and p.confidence < when.min_confidence:
        return False
    if when.max_confidence is not None and p.confidence > when.max_confidence:
        return False
    if when.min_corroboration is not None and len(p.corroborating_signals) < when.min_corroboration:
        return False
    return True


def _apply(action: RuleAction, proposed: Severity) -> Severity:
    sev = action.severity or proposed
    if action.min_severity and sev.rank < action.min_severity.rank:
        sev = action.min_severity
    if action.max_severity and sev.rank > action.max_severity.rank:
        sev = action.max_severity
    return sev


class PolicyEngine:
    def __init__(self, policy: RiskPolicy, digest: str) -> None:
        self.policy = policy
        self.digest = digest

    def match(self, facts: FindingFacts) -> tuple[str, RuleAction]:
        rule: PolicyRule
        for rule in self.policy.rules:
            if _matches(rule.when, facts):
                return rule.id, rule.then
        return "default", self.policy.default

    def decide(self, facts: FindingFacts) -> PolicyDecision:
        p = facts.proposal
        rule_id, action = self.match(facts)
        severity = _apply(action, p.severity)
        disposition = action.disposition
        confidence = p.confidence
        guardrails: list[str] = []

        # G1 — deterministic provenance failures are never accepted.
        if (facts.layer == Layer.PROVENANCE and p.deterministic and p.attack_class in PROVENANCE_FAILURE_CLASSES
                and p.severity.rank >= Severity.HIGH.rank and disposition != Disposition.QUARANTINE):
            disposition = Disposition.QUARANTINE
            severity = Severity.max(severity, Severity.CRITICAL)
            guardrails.append("G1: deterministic cryptographic/binding failure forces QUARANTINE")

        # G2 — statistical detectors without calibration never auto-quarantine.
        if not p.deterministic and not p.calibrated and disposition == Disposition.QUARANTINE:
            disposition = Disposition.REVIEW
            guardrails.append("G2: uncalibrated statistical detector capped at REVIEW")

        # G3 — metadata anomalies alone are grounds for review, not quarantine.
        if p.attack_class == "metadata_manipulation" and disposition == Disposition.QUARANTINE:
            disposition = Disposition.REVIEW
            guardrails.append("G3: metadata-only evidence capped at REVIEW")

        # G4 — automatic manipulation inference needs strong corroboration.
        if (p.attack_class == "drift_manipulation" and disposition == Disposition.QUARANTINE
                and len(p.corroborating_signals) < MANIPULATION_MIN_CORROBORATION):
            disposition = Disposition.REVIEW
            guardrails.append(f"G4: manipulation inference with < {MANIPULATION_MIN_CORROBORATION} "
                              "corroborating signals capped at REVIEW")

        # G5 — degraded execution cannot produce top-confidence statements.
        if facts.availability == Availability.DEGRADED and confidence > DEGRADED_CONFIDENCE_CAP:
            confidence = DEGRADED_CONFIDENCE_CAP
            guardrails.append(f"G5: confidence capped at {DEGRADED_CONFIDENCE_CAP} for degraded execution")

        # G6 — informational findings never quarantine.
        if severity == Severity.INFO and disposition == Disposition.QUARANTINE:
            disposition = Disposition.REVIEW
            guardrails.append("G6: INFO severity cannot quarantine")

        return PolicyDecision(rule_id=rule_id, severity=severity, disposition=disposition,
                              confidence=round(confidence, 4), rationale=action.rationale, guardrails=guardrails)
