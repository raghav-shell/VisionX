"""Clean vs attacked behaviour of the dataset detectors — detection *and* false alarms.

Assertions are invariants with margins (not exact counts) so that they test behaviour, not the
current implementation's arithmetic.
"""

from __future__ import annotations

from visionsentinel.contracts import CoverageState, ExecutionState, Severity
from visionsentinel.evidence import EvidenceStore


def _ids(findings, attack_class=None, detector=None):
    out = set()
    for f in findings:
        if (attack_class is None or f.attack_class == attack_class) and (detector is None or f.detector_id == detector):
            out.update(s.sample_id for s in f.affected_samples)
    return out


def _truth(truth, *attacks):
    return {k for k, v in truth.items() if set(v["attacks"]) & set(attacks)}


# ------------------------------------------------------------------ false-positive behaviour on clean data

def test_clean_corpus_has_no_campaign_level_findings(clean_scan):
    result, _ = clean_scan
    classes = {f.attack_class for f in result.findings if f.severity.rank >= Severity.MEDIUM.rank}
    assert "duplicate_flood" not in classes
    assert "systematic_mislabel" not in classes
    assert "duplicate_label_conflict" not in classes
    assert not [f for f in result.findings if f.attack_class == "annotation_tampering" and f.severity == Severity.HIGH]
    assert not [f for f in result.findings if "burst" in f.title.lower()]


def test_clean_corpus_sample_level_false_alarm_rates(clean_scan):
    result, _ = clean_scan
    n = sum(1 for _ in result.sections["dataset"]["contributors"]) and result.sections["dataset"]["samples"]
    assert len(_ids(result.findings, "label_flip")) / n <= 0.02
    assert len(_ids(result.findings, "ood_injection")) / n <= 0.02


# ------------------------------------------------------------------ detection on attacked data

def test_duplicate_flood_found_and_attributed(attacked_scan):
    result, _, truth = attacked_scan
    flood = _truth(truth, "duplicate_flood", "duplicate_flood_source")
    clusters = [f for f in result.findings if f.attack_class == "duplicate_flood" and f.subject.startswith("dupcluster")]
    assert len(clusters) >= 2
    for f in clusters:
        members = {s.sample_id for s in f.affected_samples}
        assert members <= flood, "a flood cluster contains a sample that was never flooded"
    contributor = [f for f in result.findings if f.subject == "dupflood-contributor:Delta"]
    assert contributor and contributor[0].affected_contributors == ["Delta"]


def test_systematic_mislabel_attributed_to_charlie(attacked_scan):
    result, _, truth = attacked_scan
    sysf = [f for f in result.findings if f.attack_class == "systematic_mislabel"]
    charlie = [f for f in sysf if f.affected_contributors == ["Charlie"]]
    assert charlie, "systematic relabelling by Charlie was not detected"
    assert len(_ids(charlie) & _truth(truth, "systematic_mislabel")) / len(_ids(charlie)) >= 0.8
    # Alpha (clean, typical imaging conditions) is never accused, and across all contributor-level transitions
    # most attributed samples are genuinely wrongly labelled (relabels, dirty-label poisons, foreign content).
    assert not [f for f in sysf if "Alpha" in f.affected_contributors]
    wrong = _truth(truth, "systematic_mislabel", "localized_trigger", "label_flip", "ood_injection")
    flagged = _ids(sysf)
    assert len(flagged & wrong) / len(flagged) >= 0.6
    # Degraded (non-semantic) mode never states a systematic campaign above MEDIUM severity.
    assert all(f.severity.rank <= Severity.MEDIUM.rank for f in sysf)


def test_label_consistency_precision(attacked_scan):
    result, _, truth = attacked_scan
    flagged = _ids(result.findings, "label_flip", "data.label_consistency")
    wrong = _truth(truth, "systematic_mislabel", "localized_trigger", "label_flip", "ood_injection")
    assert flagged, "no label inconsistencies reported on a corpus with 60+ flipped labels"
    assert len(flagged & wrong) / len(flagged) >= 0.6


def test_metadata_burst_and_sensor_change_point_at_delta(attacked_scan):
    result, _, _ = attacked_scan
    meta = [f for f in result.findings if f.attack_class == "metadata_manipulation"]
    assert any("burst" in f.title.lower() and "Delta" in f.title for f in meta)
    assert any("UAV-X9" in f.title for f in meta)
    assert all(f.recommended_disposition.value != "QUARANTINE" for f in meta)


def test_degenerate_boxes_found_for_bravo(attacked_scan):
    result, _, _ = attacked_scan
    geo = [f for f in result.findings if f.attack_class == "annotation_tampering" and f.tags.get("check") in
           {"degenerate", "outside", "clipped"}]
    assert geo and all(f.affected_contributors == ["Bravo"] for f in geo)
    assert all(f.deterministic for f in geo)


def test_injected_ood_samples_are_surfaced(attacked_scan):
    result, _, truth = attacked_scan
    ood_truth = _truth(truth, "ood_injection")
    flagged = _ids(result.findings, "ood_injection")
    assert len(flagged & ood_truth) >= len(ood_truth) // 2
    assert len(flagged - ood_truth) <= 0.02 * result.sections["dataset"]["samples"]


# ------------------------------------------------------------------ report-level invariants

def test_no_detector_errors_and_every_finding_has_verifiable_evidence(attacked_scan):
    result, ws, _ = attacked_scan
    assert not [e for e in result.executions if e.state == ExecutionState.ERROR]
    store = EvidenceStore(ws.evidence)
    for f in result.findings:
        assert f.evidence or f.evidence_unavailable_reason
        for ev in f.evidence:
            if ev.blob:
                assert store.verify(ev.blob.digest)
        assert f.policy_rule and f.policy_digest.startswith("sha256:")


def test_degraded_modes_never_claim_full_coverage(attacked_scan):
    result, _, _ = attacked_scan
    degraded = {e.detector_id for e in result.executions if e.state == ExecutionState.COMPLETED_DEGRADED}
    assert "data.label_consistency" in degraded  # no semantic encoder in this test
    rows = {r.attack_class: r for r in result.coverage.rows}
    assert rows["label_flip"].state == CoverageState.PARTIALLY_ASSESSED
    assert rows["label_flip"].recommended_evidence
    assert rows["duplicate_flood"].state == CoverageState.ASSESSED
    assert rows["clean_label_poisoning"].state == CoverageState.UNSUPPORTED


def test_scan_summary_matches_authoritative_coverage(attacked_scan):
    result, _, _ = attacked_scan
    coverage = result.coverage
    summary = result.summary
    assert coverage.total == len(coverage.rows)
    assert sum((coverage.assessed, coverage.partial, coverage.not_assessed,
                coverage.failed, coverage.unsupported)) == coverage.total
    assert summary.coverage_assessed == coverage.assessed
    assert summary.coverage_partial == coverage.partial
    assert summary.coverage_total == coverage.total
