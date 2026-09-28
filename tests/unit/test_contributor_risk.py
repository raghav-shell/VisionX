"""Contributor risk: uncertainty-aware, robust to other attackers, never a raw ratio ranking."""

from __future__ import annotations

from tests.helpers import finding
from visionsentinel.contracts import AssetType, Severity
from visionsentinel.core.detector import SampleFlag
from visionsentinel.core.profiles import ContributorPolicy
from visionsentinel.risk.contributors import SampleInfo, assess_contributors

POLICY = ContributorPolicy()


def _population(sizes: dict[str, int], flagged: dict[str, int], severity=Severity.HIGH, conf=0.9):
    samples, flags = {}, []
    for c, n in sizes.items():
        for i in range(n):
            sid = f"{c}-{i}"
            samples[sid] = SampleInfo(c, f"{c}-batch-{i // 50}")
            if i < flagged.get(c, 0):
                flags.append(SampleFlag(sid, c, "label_flip", "data.test", conf, severity))
    return samples, flags


def _by_name(result):
    return {a.contributor: a for a in result}


def test_small_contributor_is_shrunk_not_ranked_on_two_samples():
    samples, flags = _population({"Big": 500, "Tiny": 8, "A": 400, "B": 400}, {"Big": 60, "Tiny": 2, "A": 8, "B": 8})
    res = _by_name(assess_contributors(samples, flags, [], POLICY))
    assert res["Tiny"].flagged / res["Tiny"].samples > res["Big"].flagged / res["Big"].samples  # raw ratio says Tiny
    assert res["Big"].posterior_anomaly > res["Tiny"].posterior_anomaly
    assert res["Tiny"].evidence_strength in ("NONE", "LOW")
    assert res["Big"].risk_tier in ("HIGH", "CRITICAL")
    assert (res["Tiny"].credible_high - res["Tiny"].credible_low) > (res["Big"].credible_high - res["Big"].credible_low)


def test_second_attacker_does_not_hide_the_first():
    samples, flags = _population({"Heavy": 300, "Moderate": 300, "C1": 300, "C2": 300},
                                 {"Heavy": 120, "Moderate": 36, "C1": 6, "C2": 6})
    res = _by_name(assess_contributors(samples, flags, [], POLICY))
    assert res["Heavy"].risk_tier in ("HIGH", "CRITICAL")
    assert res["Moderate"].posterior_anomaly > 0.8, "median baseline must not be inflated by the heavy attacker"
    assert res["C1"].risk_tier == "LOW" and res["C2"].risk_tier == "LOW"


def test_clean_population_is_low_risk():
    samples, flags = _population({"A": 200, "B": 200, "C": 200}, {"A": 4, "B": 5, "C": 3})
    res = assess_contributors(samples, flags, [], POLICY)
    assert all(a.risk_tier == "LOW" for a in res)
    assert all(a.expected_low <= a.flagged_weighted <= a.expected_high + 1 for a in res)


def test_low_confidence_and_info_flags_are_ignored():
    samples, flags = _population({"A": 100, "B": 100, "C": 100}, {"A": 50}, conf=0.2)
    res = _by_name(assess_contributors(samples, flags, [], POLICY))
    assert res["A"].flagged == 0
    samples, flags = _population({"A": 100, "B": 100, "C": 100}, {"A": 50}, severity=Severity.INFO)
    assert _by_name(assess_contributors(samples, flags, [], POLICY))["A"].flagged == 0


def _campaign(contributor: str, count: int, severity=Severity.HIGH):
    from datetime import datetime, timezone

    from visionsentinel.contracts import Availability, Disposition, Finding, SampleRef
    base = finding(attack_class="systematic_mislabel", asset_type=AssetType.CONTRIBUTOR, asset_id=contributor,
                   affected_contributors=[contributor], severity=severity,
                   affected_samples=[SampleRef(sample_id=f"{contributor}-{i}") for i in range(count)])
    return Finding(**base.model_dump(), id=f"F-{contributor}-{count}", scan_id="S", detector_id="data.x",
                   detector_version="1.0.0", proposed_severity=severity, recommended_disposition=Disposition.REVIEW,
                   availability=Availability.READY, policy_rule="r", policy_digest="sha256:" + "0" * 64,
                   created_at=datetime.now(timezone.utc))


def test_campaign_findings_raise_tier_but_single_sample_findings_do_not():
    samples, flags = _population({"A": 200, "B": 200, "C": 200}, {})
    res = _by_name(assess_contributors(samples, flags, [_campaign("A", 12)], POLICY))
    assert res["A"].risk_tier == "HIGH" and res["A"].campaign_findings
    res = _by_name(assess_contributors(samples, flags, [_campaign("B", 1)], POLICY))
    assert res["B"].risk_tier == "LOW" and not res["B"].campaign_findings


def test_batch_breakdown_and_rationale_present():
    samples, flags = _population({"A": 120, "B": 120, "C": 120}, {"A": 40})
    a = _by_name(assess_contributors(samples, flags, [], POLICY))["A"]
    assert sum(b["samples"] for b in a.batches.values()) == 120
    assert sum(b["flagged"] for b in a.batches.values()) == 40
    assert any("Expected under the baseline" in r for r in a.rationale)
    assert "label inconsistency" in a.dominant_signals
