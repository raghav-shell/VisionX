"""Risk policy and guardrail invariants."""

from __future__ import annotations

import pytest

from tests.helpers import finding
from visionsentinel.contracts import Availability, Disposition, Layer, Severity
from visionsentinel.core import load_profile
from visionsentinel.risk.policy import FindingFacts, PolicyEngine


@pytest.fixture(scope="module")
def engine() -> PolicyEngine:
    p = load_profile("baseline")
    return PolicyEngine(p.risk, p.policy_digest)


def facts(layer=Layer.DATA, availability=Availability.READY, detector="data.x", **over) -> FindingFacts:
    return FindingFacts(finding(**over), detector, layer, availability)


@pytest.mark.parametrize("cls", ["record_modification", "record_deletion", "record_replay", "signature_forgery",
                                 "model_binding_violation", "record_truncation", "record_reorder"])
def test_signature_or_chain_failure_never_accepted(engine, cls):
    d = engine.decide(facts(Layer.PROVENANCE, attack_class=cls, severity=Severity.HIGH, deterministic=True,
                            confidence=1.0))
    assert d.disposition == Disposition.QUARANTINE
    assert d.severity == Severity.CRITICAL
    assert d.rule_id == "provenance.failure"


def test_guardrail_overrides_permissive_policy_for_crypto_failure():
    from visionsentinel.core.profiles import RiskPolicy, RuleAction

    lax = RiskPolicy(rules=[], default=RuleAction(disposition=Disposition.ACCEPT, rationale="accept everything"))
    d = PolicyEngine(lax, "x").decide(facts(Layer.PROVENANCE, attack_class="signature_forgery",
                                            severity=Severity.HIGH, deterministic=True))
    assert d.disposition == Disposition.QUARANTINE
    assert any(g.startswith("G1") for g in d.guardrails)


def test_uncalibrated_detector_never_auto_quarantines(engine):
    d = engine.decide(facts(severity=Severity.CRITICAL, confidence=0.99, calibrated=False, deterministic=False,
                            corroborating_signals=["a", "b", "c"]))
    assert d.disposition == Disposition.REVIEW
    assert any(g.startswith("G2") for g in d.guardrails)
    cal = engine.decide(facts(severity=Severity.CRITICAL, confidence=0.99, calibrated=True, deterministic=False,
                              corroborating_signals=["a", "b"]))
    assert cal.disposition == Disposition.QUARANTINE and cal.rule_id == "corroborated.high"


def test_metadata_only_capped_at_review(engine):
    d = engine.decide(facts(attack_class="metadata_manipulation", severity=Severity.CRITICAL, confidence=1.0,
                            deterministic=True, corroborating_signals=["a", "b", "c"]))
    assert d.disposition == Disposition.REVIEW
    assert d.severity.rank <= Severity.MEDIUM.rank


def test_drift_manipulation_requires_three_corroborating_signals():
    from visionsentinel.core.profiles import RiskPolicy, RuleAction

    harsh = PolicyEngine(RiskPolicy(rules=[], default=RuleAction(disposition=Disposition.QUARANTINE,
                                                                 rationale="quarantine all")), "x")
    weak = harsh.decide(facts(Layer.DRIFT, attack_class="drift_manipulation", calibrated=True,
                              corroborating_signals=["a", "b"]))
    assert weak.disposition == Disposition.REVIEW
    strong = harsh.decide(facts(Layer.DRIFT, attack_class="drift_manipulation", calibrated=True,
                                corroborating_signals=["a", "b", "c"]))
    assert strong.disposition == Disposition.QUARANTINE


def test_degraded_execution_caps_confidence(engine):
    d = engine.decide(facts(availability=Availability.DEGRADED, confidence=0.99))
    assert d.confidence <= 0.85


def test_approved_model_digest_is_accept(engine):
    d = engine.decide(facts(Layer.MODEL, attack_class="model_substitution", severity=Severity.INFO,
                            deterministic=True, confidence=1.0))
    assert d.disposition == Disposition.ACCEPT and d.rule_id == "model.approved-match"


def test_digest_and_behaviour_mismatch_is_critical_quarantine(engine):
    d = engine.decide(facts(Layer.MODEL, attack_class="behavioural_divergence", severity=Severity.HIGH,
                            deterministic=True, confidence=0.97, corroborating_signals=["artifact digest mismatch"]))
    assert (d.severity, d.disposition) == (Severity.CRITICAL, Disposition.QUARANTINE)


def test_every_decision_names_its_rule(engine):
    for sev in Severity:
        d = engine.decide(facts(severity=sev))
        assert d.rule_id and d.rationale
