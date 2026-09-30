from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.helpers import finding, make_spec
from visionsentinel.contracts import (
    ATTACK_CLASSES,
    AttackSupport,
    CoverageRow,
    CoverageState,
    CoverageStatement,
    Disposition,
    Layer,
    Severity,
    SupportLevel,
    UnsupportedAttack,
)


def _coverage_rows():
    rows = list(ATTACK_CLASSES.values())[:len(CoverageState)]
    return [CoverageRow(attack_class=info.id, layer=info.layer, title=info.title,
                        state=state, reason="test") for info, state in zip(rows, CoverageState)]


def _valid_coverage():
    rows = _coverage_rows()
    counts = {state: sum(row.state is state for row in rows) for state in CoverageState}
    return CoverageStatement(rows=rows, total=len(rows), assessed=counts[CoverageState.ASSESSED],
                             partial=counts[CoverageState.PARTIALLY_ASSESSED],
                             not_assessed=counts[CoverageState.NOT_ASSESSED],
                             failed=counts[CoverageState.FAILED_TO_EXECUTE],
                             unsupported=counts[CoverageState.UNSUPPORTED])


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


def test_coverage_statement_validates_rows_and_aggregates():
    coverage = _valid_coverage()
    assert coverage.total == len(coverage.rows)
    assert sum((coverage.assessed, coverage.partial, coverage.not_assessed,
                coverage.failed, coverage.unsupported)) == coverage.total


@pytest.mark.parametrize("field", ["assessed", "partial", "not_assessed", "failed", "unsupported"])
def test_coverage_statement_rejects_incorrect_state_count(field):
    coverage = _valid_coverage().model_dump()
    coverage[field] += 1
    with pytest.raises(ValidationError, match="coverage"):
        CoverageStatement.model_validate(coverage)


def test_coverage_statement_rejects_wrong_total_duplicate_rows_and_sum_mismatch():
    valid = _valid_coverage().model_dump()
    with pytest.raises(ValidationError, match="total"):
        CoverageStatement.model_validate({**valid, "total": valid["total"] + 1})

    duplicate = {**valid, "rows": valid["rows"] + [valid["rows"][0]], "total": valid["total"] + 1}
    with pytest.raises(ValidationError, match="duplicate"):
        CoverageStatement.model_validate(duplicate)

    # A sum mismatch necessarily also violates the row/total invariant once the
    # state counters are otherwise correct; both invariants must reject it.
    with pytest.raises(ValidationError, match="total"):
        CoverageStatement.model_validate({**valid, "total": valid["total"] + 1})
