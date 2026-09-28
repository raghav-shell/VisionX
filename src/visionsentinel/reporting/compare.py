"""Scan comparison: what changed between two assurance runs, and why."""

from __future__ import annotations

from typing import Any

from ..contracts import Disposition, ScanResult, Severity


def _key(f) -> tuple[str, str]:
    return f.detector_id, f.subject


def compare_scans(a: ScanResult, b: ScanResult) -> dict[str, Any]:
    fa = {_key(f): f for f in a.findings}
    fb = {_key(f): f for f in b.findings}
    new = [fb[k] for k in fb.keys() - fa.keys() if fb[k].severity != Severity.INFO]
    resolved = [fa[k] for k in fa.keys() - fb.keys() if fa[k].severity != Severity.INFO]
    changed = []
    for k in fa.keys() & fb.keys():
        x, y = fa[k], fb[k]
        if x.severity != y.severity or x.recommended_disposition != y.recommended_disposition:
            changed.append({"detector": k[0], "subject": k[1], "title": y.title,
                            "severity": [x.severity.value, y.severity.value],
                            "disposition": [x.recommended_disposition.value, y.recommended_disposition.value]})
    ca = {r.attack_class: r.state.value for r in a.coverage.rows}
    cb = {r.attack_class: r.state.value for r in b.coverage.rows}
    coverage_changes = [{"attack_class": k, "from": ca.get(k), "to": cb.get(k)} for k in cb if ca.get(k) != cb.get(k)]

    def digests(r: ScanResult) -> dict[str, str | None]:
        return {a_.role.value: a_.digest for a_ in r.assets}

    da, db = digests(a), digests(b)
    asset_changes = [{"role": role, "from": da.get(role), "to": db.get(role),
                      "status": "changed" if da.get(role) and db.get(role) and da[role] != db[role] else
                      ("added" if role not in da else ("removed" if role not in db else "unchanged"))}
                     for role in sorted(set(da) | set(db))]

    def drift(r: ScanResult) -> float | None:
        cov = r.sections.get("drift.covariate", {}).get("covariate")
        return max((abs(x["cliffs_delta"]) for x in cov["axes"]), default=0.0) if cov else None

    def count(r: ScanResult, sev: Severity | None = None, disp: Disposition | None = None) -> int:
        return sum(1 for f in r.findings if (sev is None or f.severity == sev)
                   and (disp is None or f.recommended_disposition == disp))

    cov_pct = (lambda r: round(100 * r.coverage.assessed / r.coverage.total) if r.coverage.total else 0)
    tiers_a = {c.contributor: c.risk_tier for c in a.contributors}
    tiers_b = {c.contributor: c.risk_tier for c in b.contributors}
    explanation = []
    for ch in asset_changes:
        if ch["status"] != "unchanged":
            explanation.append(f"{ch['role'].replace('_', ' ').lower()} {ch['status']}")
    if new:
        explanation.append(f"{len(new)} new finding(s), e.g. '{new[0].title}'")
    if resolved:
        explanation.append(f"{len(resolved)} finding(s) no longer present, e.g. '{resolved[0].title}'")
    for k in sorted(set(tiers_a) | set(tiers_b)):
        if tiers_a.get(k) != tiers_b.get(k):
            explanation.append(f"contributor {k}: {tiers_a.get(k, '—')} → {tiers_b.get(k, '—')}")
    return {
        "a": {"scan_id": a.scan_id, "name": a.name, "created_at": a.created_at.isoformat()},
        "b": {"scan_id": b.scan_id, "name": b.name, "created_at": b.created_at.isoformat()},
        "summary": {
            "coverage_pct": [cov_pct(a), cov_pct(b)],
            "critical": [count(a, Severity.CRITICAL), count(b, Severity.CRITICAL)],
            "quarantine": [count(a, disp=Disposition.QUARANTINE), count(b, disp=Disposition.QUARANTINE)],
            "review": [count(a, disp=Disposition.REVIEW), count(b, disp=Disposition.REVIEW)],
            "drift_max_delta": [drift(a), drift(b)],
            "overall": [a.summary.overall_disposition.value if a.summary else None,
                        b.summary.overall_disposition.value if b.summary else None],
        },
        "new_findings": [{"id": f.id, "title": f.title, "severity": f.severity.value,
                          "disposition": f.recommended_disposition.value, "detector": f.detector_id} for f in new],
        "resolved_findings": [{"id": f.id, "title": f.title, "severity": f.severity.value, "detector": f.detector_id}
                              for f in resolved],
        "changed_findings": changed,
        "coverage_changes": coverage_changes,
        "asset_changes": asset_changes,
        "contributor_changes": [{"contributor": k, "from": tiers_a.get(k), "to": tiers_b.get(k)}
                                for k in sorted(set(tiers_a) | set(tiers_b)) if tiers_a.get(k) != tiers_b.get(k)],
        "explanation": explanation or ["no material change"],
    }
