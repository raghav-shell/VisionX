"""Contributor risk: a Beta–Binomial model instead of a raw flagged/total ratio.

For contributor *c* with ``n`` samples and (confidence × severity weighted) flagged mass ``f``:

* baseline ``p̄`` = median of the *other* contributors' flag rates (robust leave-one-out: neither the
  contributor itself nor a second heavy attacker can inflate the baseline it is judged against, as long
  as attackers are not the majority of contributors);
* prior ``θ ~ Beta(κ·p̄, κ·(1 − p̄))`` with profile-defined strength κ (pseudo-samples), so small
  contributors are shrunk towards the baseline instead of being ranked on two samples;
* posterior ``Beta(κ·p̄ + f, κ·(1 − p̄) + n − f)``;
* posterior anomaly ``P(θ > k·p̄ | data)`` for the profile's excess factor k;
* expected flags: the central interval of the Beta-Binomial posterior predictive under the baseline;
* campaign findings — group-level findings (≥ 3 samples) of a campaign class attributed to this
  contributor alone — raise the risk tier independently of the sample counts.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from scipy import stats as sps

from ..contracts import ContributorAssessment, Disposition, Finding, Severity
from ..core.detector import SampleFlag
from ..core.profiles import ContributorPolicy

SEVERITY_WEIGHT = {Severity.INFO: 0.0, Severity.LOW: 0.5, Severity.MEDIUM: 0.75, Severity.HIGH: 1.0,
                   Severity.CRITICAL: 1.0}

SIGNAL_NAMES = {
    "label_flip": "label inconsistency", "systematic_mislabel": "systematic label inconsistency",
    "duplicate_flood": "duplicate flooding", "duplicate_label_conflict": "conflicting duplicate labels",
    "localized_trigger": "trigger-pattern correlation", "blended_trigger": "blended-pattern correlation",
    "ood_injection": "out-of-distribution content", "annotation_tampering": "annotation geometry",
    "metadata_manipulation": "metadata anomalies", "corrupted_samples": "corrupted files",
}

MIN_CAMPAIGN_SAMPLES = 3
CAMPAIGN_CLASSES = {"systematic_mislabel", "duplicate_flood", "localized_trigger", "blended_trigger",
                    "duplicate_label_conflict", "annotation_tampering", "ood_injection"}


@dataclass(frozen=True)
class SampleInfo:
    contributor: str | None
    batch: str | None


def assess_contributors(samples: dict[str, SampleInfo], flags: list[SampleFlag], findings: list[Finding],
                        policy: ContributorPolicy) -> list[ContributorAssessment]:
    weight: dict[str, float] = defaultdict(float)
    per_sample_classes: dict[str, dict[str, float]] = defaultdict(dict)
    for fl in flags:
        if fl.sample_id not in samples:
            continue
        if fl.confidence < policy.flag_min_confidence or fl.severity.rank < policy.flag_min_severity.rank:
            continue
        w = min(1.0, fl.confidence * SEVERITY_WEIGHT[fl.severity])
        weight[fl.sample_id] = max(weight[fl.sample_id], w)
        per_sample_classes[fl.sample_id][fl.attack_class] = max(per_sample_classes[fl.sample_id].get(fl.attack_class, 0), w)

    by_contrib: dict[str, list[str]] = defaultdict(list)
    for sid, info in samples.items():
        if info.contributor:
            by_contrib[info.contributor].append(sid)
    if len(by_contrib) < 2:
        return []
    totals = {c: (len(ids), sum(weight.get(s, 0.0) for s in ids)) for c, ids in by_contrib.items()}
    rates = {c: (f + 0.5) / (n + 1.0) for c, (n, f) in totals.items()}

    out: list[ContributorAssessment] = []
    for c, ids in sorted(by_contrib.items()):
        n, f = totals[c]
        base = float(np.median([r for other, r in rates.items() if other != c]))
        kappa = policy.prior_strength
        a0, b0 = kappa * base, kappa * (1 - base)
        a1, b1 = a0 + f, b0 + max(n - f, 0.0)
        post = sps.beta(a1, b1)
        tail = (1 - policy.credible_level) / 2
        cred_lo, cred_hi = float(post.ppf(tail)), float(post.ppf(1 - tail))
        threshold = min(0.999, policy.excess_factor * base)
        anomaly = float(post.sf(threshold))
        pred = sps.betabinom(n, a0, b0)
        exp_lo, exp_hi = int(pred.ppf(tail)), int(pred.ppf(1 - tail))
        flagged = sum(1 for s in ids if weight.get(s, 0) > 0)

        if n < policy.min_samples:
            strength = "LOW" if anomaly >= policy.medium_anomaly else "NONE"
        elif anomaly >= policy.high_anomaly and f > exp_hi:
            strength = "HIGH"
        elif anomaly >= policy.medium_anomaly:
            strength = "MEDIUM"
        elif anomaly >= 0.5:
            strength = "LOW"
        else:
            strength = "NONE"

        breakdown: dict[str, float] = defaultdict(float)
        for s in ids:
            for cls, w in per_sample_classes.get(s, {}).items():
                breakdown[SIGNAL_NAMES.get(cls, cls)] += w
        dominant = [k for k, _ in sorted(breakdown.items(), key=lambda kv: -kv[1]) if breakdown[k] >= 1.0][:3]

        campaigns = [x for x in findings if x.affected_contributors == [c] and x.attack_class in CAMPAIGN_CLASSES
                     and x.affected_count >= MIN_CAMPAIGN_SAMPLES and x.severity.rank >= Severity.MEDIUM.rank]
        high_campaigns = [x for x in campaigns if x.severity.rank >= Severity.HIGH.rank]
        rationale = [
            f"{flagged} of {n} samples flagged (weighted mass {f:.1f}); baseline (median of other contributors) {base:.2%}.",
            f"Expected under the baseline: {exp_lo}–{exp_hi} flags ({policy.credible_level:.0%} predictive interval).",
            f"Posterior flag rate {a1 / (a1 + b1):.2%} ({policy.credible_level:.0%} credible interval "
            f"{cred_lo:.2%}–{cred_hi:.2%}); P(rate > {policy.excess_factor:g}× baseline) = {anomaly:.2f}.",
        ]
        if n < policy.min_samples:
            rationale.append(f"Only {n} samples (< {policy.min_samples}): evidence strength capped.")
        if campaigns:
            rationale.append("Attributed campaign findings: " + "; ".join(x.title for x in campaigns[:5]) + ".")

        if (strength == "HIGH" and len(high_campaigns) >= 2) or any(x.severity == Severity.CRITICAL for x in campaigns):
            tier = "CRITICAL"
        elif strength == "HIGH" or high_campaigns:
            tier = "HIGH"
        elif strength == "MEDIUM" or campaigns:
            tier = "ELEVATED"
        else:
            tier = "LOW"
        action = {"CRITICAL": Disposition.QUARANTINE, "HIGH": Disposition.QUARANTINE if high_campaigns else Disposition.REVIEW,
                  "ELEVATED": Disposition.REVIEW, "LOW": Disposition.ACCEPT}[tier]

        batches: dict[str, dict[str, int]] = defaultdict(lambda: {"samples": 0, "flagged": 0})
        for s in ids:
            b = samples[s].batch or "unbatched"
            batches[b]["samples"] += 1
            batches[b]["flagged"] += int(weight.get(s, 0) > 0)

        out.append(ContributorAssessment(
            contributor=c, samples=n, flagged=flagged, flagged_weighted=round(f, 3), baseline_rate=round(base, 5),
            expected_low=exp_lo, expected_high=exp_hi, posterior_mean=round(a1 / (a1 + b1), 5),
            credible_low=round(cred_lo, 5), credible_high=round(cred_hi, 5), posterior_anomaly=round(anomaly, 4),
            evidence_strength=strength, risk_tier=tier, dominant_signals=dominant,  # type: ignore[arg-type]
            signal_breakdown={k: round(v, 2) for k, v in breakdown.items()},
            campaign_findings=[x.id for x in campaigns], batches=dict(batches), recommended_action=action,
            rationale=rationale))
    tier_rank = {"CRITICAL": 3, "HIGH": 2, "ELEVATED": 1, "LOW": 0}
    out.sort(key=lambda a: (-tier_rank[a.risk_tier], -a.posterior_anomaly, -a.flagged_weighted))
    return out
