from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.helpers import finding, make_spec
from visionsentinel.contracts import (
    ATTACK_CLASSES,
    AttackSupport,
    Disposition,
    Layer,
    Severity,
    SupportLevel,
    UnsupportedAttack,
)


def test_severity_and_disposition_have_total_order():
    assert Severity.max(Severity.LOW, Severity.CRITICAL, Severity.MEDIUM) is Severity.CRITICAL
    assert [s.rank for s in Severity] == sorted(s.rank for s in Severity)
    assert Disposition.max(Disposition.ACCEPT, Disposition.QUARANTINE) is Disposition.QUARANTINE
    assert Disposition.min(Disposition.REVIEW, Disposition.ACCEPT) is Disposition.ACCEPT


def test_finding_requires_evidence_or_explicit_unavailability():
    with pytest.raises(ValidationError, match="evidence"):
        finding(evidence=[])
    f = finding(evidence=[], evidence_unavailable_reason="black-box access only; no internal evidence")
    assert f.evidence_unavailable_reason


def test_finding_rejects_unknown_attack_class_and_unknown_fields():
    with pytest.raises(ValidationError):
        finding(attack_class="made_up_attack")
    with pytest.raises(ValidationError):
        finding(sneaky_field=1)


def test_finding_reason_must_be_a_sentence_not_a_bare_score():
    with pytest.raises(ValidationError):
        finding(reason="score 0.93")


def test_confidence_is_bounded():
    with pytest.raises(ValidationError):
        finding(confidence=1.2)


def test_spec_rejects_class_both_supported_and_unsupported():
    with pytest.raises(ValidationError, match="both supported and unsupported"):
        spec = make_spec("test.bad")
        type(spec).model_validate({
            **spec.model_dump(),
            "unsupported": [UnsupportedAttack(attack_class="label_flip", reason="x").model_dump()],
        })


def test_spec_id_and_version_format_enforced():
    with pytest.raises(ValidationError):
        make_spec("NoDot")
    with pytest.raises(ValidationError):
        AttackSupport(attack_class="nope", level=SupportLevel.FULL)


def test_attack_catalogue_is_consistent():
    layers = {a.layer for a in ATTACK_CLASSES.values()}
    assert layers == set(Layer)
    for a in ATTACK_CLASSES.values():
        if a.unsupported_reason:
            assert a.recommended_evidence, f"{a.id} is unsupported but recommends no evidence"
