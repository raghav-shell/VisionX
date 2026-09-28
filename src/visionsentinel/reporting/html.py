"""Self-contained HTML assurance report.

Security properties: a restrictive Content-Security-Policy meta tag (no scripts, no network: images only as
``data:`` URIs), every string that originates from assets, metadata, evidence or users passed through
``html.escape``, and evidence images embedded only after their SHA-256 has been re-verified.
"""

from __future__ import annotations

import base64
from html import escape
from typing import Any

from .. import __version__
from ..contracts import ATTACK_CLASSES, CoverageState, Disposition, ScanResult, Severity
from ..core.errors import EvidenceIntegrityError
from ..evidence.store import EvidenceStore

MAX_FINDINGS_DETAILED = 120
MAX_IMAGES = 60

CSS = """
:root{--ink:#16191d;--muted:#5d6673;--line:#d9dde3;--panel:#f5f6f8;--accent:#0f7c99;--crit:#b3261e;--high:#c2410c;
--med:#a16207;--low:#0f766e;--ok:#2f7d4f;--head:#101317}
*{box-sizing:border-box}body{margin:0;font:13px/1.5 "IBM Plex Sans","Segoe UI",system-ui,sans-serif;color:var(--ink);
background:#fff}header{background:var(--head);color:#e8eaed;padding:28px 40px}header h1{margin:0;font-size:22px;
letter-spacing:.02em}header .sub{color:#9aa3ad;font-size:12px;letter-spacing:.12em;text-transform:uppercase}
main{padding:24px 40px 60px;max-width:1180px}h2{font-size:15px;letter-spacing:.08em;text-transform:uppercase;
border-bottom:2px solid var(--ink);padding-bottom:6px;margin-top:36px}h3{font-size:14px;margin:18px 0 6px}
table{border-collapse:collapse;width:100%;margin:8px 0 12px;font-size:12px}th,td{border-bottom:1px solid var(--line);
padding:5px 8px;text-align:left;vertical-align:top}th{background:var(--panel);font-weight:600;font-size:11px;
text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}code,.mono{font-family:"IBM Plex Mono",Consolas,
monospace;font-size:11.5px;word-break:break-all}.badge{display:inline-block;padding:1px 8px;border-radius:3px;
font-size:11px;font-weight:600;letter-spacing:.04em;border:1px solid currentColor}.CRITICAL,.QUARANTINE,.FAILED,
.FAILED_TO_EXECUTE,.ERROR{color:var(--crit)}.HIGH{color:var(--high)}.MEDIUM,.REVIEW,.PARTIALLY_ASSESSED,
.DEGRADED,.COMPLETED_DEGRADED,.ABSTAINED{color:var(--med)}.LOW{color:var(--low)}.INFO,.NOT_ASSESSED,
.UNSUPPORTED,.NOT_RUN,.UNAVAILABLE,.BUDGET_EXCLUDED{color:var(--muted)}.ACCEPT,.ASSESSED,.READY,.COMPLETED,
.VALID{color:var(--ok)}.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:14px 0}
.kpi{background:var(--panel);border:1px solid var(--line);padding:10px 12px}.kpi b{display:block;font-size:22px}
.kpi span{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}.finding{border:1px solid
var(--line);border-left:4px solid var(--muted);padding:10px 14px;margin:10px 0;page-break-inside:avoid}
.finding.sev-CRITICAL{border-left-color:var(--crit)}.finding.sev-HIGH{border-left-color:var(--high)}
.finding.sev-MEDIUM{border-left-color:var(--med)}.finding.sev-LOW{border-left-color:var(--low)}
.finding img{max-width:100%;border:1px solid var(--line);margin-top:6px;image-rendering:pixelated}
.note{background:#fff8e6;border:1px solid #f0d58c;padding:10px 14px;margin:12px 0}.small{color:var(--muted);
font-size:11.5px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}footer{color:var(--muted);font-size:11px;
padding:20px 40px;border-top:1px solid var(--line)}@media print{header{-webkit-print-color-adjust:exact}}
"""


def e(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def badge(value: Any) -> str:
    v = getattr(value, "value", value)
    return f'<span class="badge {e(v)}">{e(v)}</span>'


def _table(headers: list[str], rows: list[list[Any]], raw_cols: set[int] | None = None) -> str:
    raw_cols = raw_cols or set()
    head = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c if i in raw_cols else e(c)}</td>" for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


class _Images:
    def __init__(self, store: EvidenceStore | None) -> None:
        self.store, self.count = store, 0

    def img(self, digest: str | None, alt: str) -> str:
        if not digest or self.store is None or self.count >= MAX_IMAGES:
            return f'<div class="small mono">evidence {e(digest)}</div>' if digest else ""
        try:
            data = self.store.get(digest)
        except EvidenceIntegrityError as exc:
            return f'<div class="note"><b>EVIDENCE INTEGRITY FAILURE</b> — {e(exc)}</div>'
        if not data.startswith(b"\x89PNG"):
            return ""
        self.count += 1
        return f'<img alt="{e(alt)}" src="data:image/png;base64,{base64.b64encode(data).decode()}">'


def render(result: ScanResult, store: EvidenceStore | None, *, manifest_note: str = "") -> str:
    s = result.summary
    images = _Images(store)
    sec = result.sections
    parts: list[str] = []
    add = parts.append

    add(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>VisionSentinel report {e(result.scan_id)}</title>
<style>{CSS}</style></head><body><header><div class="sub">VisionSentinel · Air-gapped computer-vision integrity &amp;
assurance</div><h1>Assurance report — {e(result.name)}</h1><div class="mono" style="color:#9aa3ad;margin-top:6px">
{e(result.scan_id)} · profile {e(result.profile)} ({e(result.budget.value)}) · sealed {e(result.completed_at)}</div>
</header><main>""")

    # 1 executive summary
    by_disp = s.by_disposition if s else {}
    crit = s.by_severity.get(Severity.CRITICAL, 0) if s else 0
    add("<h2>1 · Executive assurance summary</h2>")
    add(f"""<p>Overall recommended disposition: {badge(s.overall_disposition if s else '—')}.
This report states what was assessed, on which evidence and under which assumptions. It does <b>not</b> certify that
the assessed assets are secure; attack classes that were not or could not be assessed are listed in sections 10–11.</p>
<div class="kpis"><div class="kpi"><b>{e(s.findings if s else 0)}</b><span>findings</span></div>
<div class="kpi"><b class="CRITICAL">{e(crit)}</b><span>critical</span></div>
<div class="kpi"><b class="QUARANTINE">{e(by_disp.get(Disposition.QUARANTINE, 0))}</b><span>quarantine</span></div>
<div class="kpi"><b class="REVIEW">{e(by_disp.get(Disposition.REVIEW, 0))}</b><span>review</span></div>
<div class="kpi"><b>{e(s.coverage_assessed if s else 0)}/{e(s.coverage_total if s else 0)}</b>
<span>attack classes fully assessed ({e(s.coverage_partial if s else 0)} partial)</span></div></div>""")
    top = [f for f in result.findings if f.severity.rank >= Severity.HIGH.rank][:8]
    if top:
        add(_table(["severity", "disposition", "finding", "detector"],
                   [[badge(f.severity), badge(f.recommended_disposition), e(f.title), e(f.detector_id)] for f in top],
                   raw_cols={0, 1, 2, 3}))
    if result.contributors:
        c0 = result.contributors[0]
        add(f"<p>Highest-risk contributor: <b>{e(c0.contributor)}</b> — tier {badge(c0.risk_tier)}, posterior anomaly "
            f"{c0.posterior_anomaly:.2f}, {c0.flagged} of {c0.samples} samples flagged (expected {c0.expected_low}–"
            f"{c0.expected_high}).</p>")

    # 2 assets
    add("<h2>2 · Assets assessed</h2>")
    add(_table(["role", "name", "format", "sha256 digest"],
               [[a.role.value, a.name, a.format, f'<span class="mono">{e(a.digest)}</span>'] for a in result.assets],
               raw_cols={3}))

    # 3 access assumptions
    add("<h2>3 · Access assumptions</h2><ul>")
    assumptions = list(dict.fromkeys(x for f in result.findings for x in f.access_assumptions))
    for a in assumptions or ["No findings; see detector declarations for assumptions."]:
        add(f"<li>{e(a)}</li>")
    withheld = [c.capability.value for c in result.capabilities if c.withheld]
    if withheld:
        add(f"<li>Capabilities withheld by profile policy: {e(', '.join(withheld))}</li>")
    add("</ul>")

    # 4 capability plan
    add("<h2>4 · Capability plan</h2><div class='grid2'><div>")
    add(_table(["capability", "state", "source / note"],
               [[c.capability.value, badge("WITHHELD" if c.withheld else ("READY" if c.present else "UNAVAILABLE")),
                 e(c.note or c.source or "")] for c in result.capabilities], raw_cols={1, 2}))
    add("</div><div>")
    add(_table(["detector", "planned", "executed", "mode", "time"],
               [[e(x.detector_id), badge(x.planned), badge(x.state), e(x.mode or "—"), f"{x.runtime_ms / 1000:.2f}s"]
                for x in result.executions], raw_cols={0, 1, 2, 3}))
    add("</div></div>")
    not_run = [x for x in result.executions if x.state.value in ("NOT_RUN", "ERROR", "ABSTAINED")]
    if not_run:
        add(_table(["detector", "state", "reason"], [[x.detector_id, badge(x.state), e("; ".join(x.reasons))]
                                                     for x in not_run], raw_cols={1, 2}))

    # 5 findings
    add(f"<h2>5 · Findings ({len(result.findings)})</h2>")
    for i, f in enumerate(result.findings):
        if i >= MAX_FINDINGS_DETAILED:
            add(f"<p class='small'>{len(result.findings) - i} further findings are listed in report.json.</p>")
            break
        ev_html = []
        for ev in f.evidence[:4]:
            ev_html.append(f"<div class='small'><b>{e(ev.title)}</b> — {e(ev.summary)}</div>")
            if ev.blob and ev.blob.media_type == "image/png":
                ev_html.append(images.img(ev.blob.digest, ev.title))
        if not f.evidence:
            ev_html.append(f"<div class='small'>Evidence unavailable: {e(f.evidence_unavailable_reason)}</div>")
        add(f"""<div class="finding sev-{e(f.severity.value)}"><div>{badge(f.severity)} {badge(f.recommended_disposition)}
<b>{e(f.title)}</b> <span class="small mono">{e(f.id)}</span></div><p>{e(f.reason)}</p>
<div class="small">Detector <code>{e(f.detector_id)}</code> v{e(f.detector_version)} · availability {e(f.availability.value)}
· confidence {f.confidence:.2f}{' · raw score ' + e(f.raw_score) if f.raw_score is not None else ''}
{' (threshold ' + e(f.threshold) + ')' if f.threshold is not None else ''} · policy rule <code>{e(f.policy_rule)}</code>
{' · guardrails: ' + e('; '.join(f.guardrails)) if f.guardrails else ''} · {'calibrated' if f.calibrated else 'uncalibrated'}
{' · affected: ' + e(f.affected_count) if f.affected_count else ''}</div>{''.join(ev_html)}
<div class="small"><b>Recommended action:</b> {e(f.recommended_action)}</div></div>""")

    # 6 contributors
    add("<h2>6 · Contributor assessment</h2>")
    if result.contributors:
        add(_table(["contributor", "samples", "flagged", "expected", "posterior rate (CI)", "P(anomalous)", "evidence",
                    "tier", "action", "dominant signals"],
                   [[c.contributor, c.samples, c.flagged, f"{c.expected_low}–{c.expected_high}",
                     f"{c.posterior_mean:.1%} ({c.credible_low:.1%}–{c.credible_high:.1%})", f"{c.posterior_anomaly:.2f}",
                     c.evidence_strength, badge(c.risk_tier), badge(c.recommended_action), ", ".join(c.dominant_signals)]
                    for c in result.contributors], raw_cols={7, 8}))
    else:
        add("<p class='small'>No contributor attribution was available.</p>")

    # 7 model integrity
    add("<h2>7 · Model integrity</h2>")
    ident = sec.get("model.artifact_digest", {}).get("identity")
    if ident:
        cand = ident["candidate"]
        add(_table(["check", "result"], [["artifact digest", f"<span class='mono'>{e(cand['artifact_digest'])}</span>"],
                                         ["artifact matches approved", badge("ASSESSED" if ident["artifact_match"] else "FAILED")],
                                         ["parameters match approved", badge("ASSESSED" if ident["param_match"] else "FAILED")],
                                         ["sandbox isolation", e(ident.get("isolation"))]], raw_cols={1}))
    beh = sec.get("model.behaviour_fingerprint", {}).get("behaviour")
    if beh:
        o = beh["overall"]
        add(f"<p>Behavioural fingerprint against {e(beh['reference'])}: {o['probes']} probes, top-1 agreement "
            f"{o['agreement']:.1%}, mean JSD {o['jsd_mean']:.2e}, Kendall τ {o['kendall_tau']:.3f}.</p>")
    nc = sec.get("model.trigger_reconstruction", {}).get("reconstruction")
    if nc:
        add(_table(["class", "trigger L1 (px)", "anomaly index"],
                   [[c, f"{l1:.1f}", f"{a:+.2f}"] for c, l1, a in zip(nc["classes"], nc["l1"], nc["anomaly_index"])]))
        add(f"<p class='small'>Threshold {e(nc['threshold'])} — {e(nc['threshold_origin'])}</p>")
    if not (ident or beh or nc):
        add("<p class='small'>No model was assessed.</p>")

    # 8 provenance
    add("<h2>8 · Provenance state</h2>")
    led = sec.get("provenance.ledger_integrity", {}).get("ledger")
    if led:
        c = led["counts"]
        add(f"<p>Ledger <span class='mono'>{e(led['ledger_id'])}</span>: {badge('VALID' if led['intact'] else 'FAILED')} "
            f"{c['VALID']} valid · {c['FAILED']} failed · {c['UNTRUSTED']} untrusted; trust root "
            f"<span class='mono'>{e(led['trust_root'])}</span>.</p>")
        bad = [r for r in led["records"] if r["status"] != "VALID"][:40]
        if bad:
            add(_table(["sequence", "status", "reasons"], [[r["seq"], badge(r["status"]), e("; ".join(r["reasons"]))]
                                                           for r in bad], raw_cols={1, 2}))
        add(_table(["anchor line", "tree size", "status"], [[a.get("line"), a.get("tree_size"), badge(a["status"])]
                                                            for a in led["anchors"]], raw_cols={2}))
    else:
        add("<p class='small'>No inference ledger was assessed.</p>")

    # 9 drift
    add("<h2>9 · Drift assessment</h2>")
    cov = sec.get("drift.covariate", {}).get("covariate")
    interp = sec.get("drift.interpretation", {}).get("interpretation")
    if cov:
        if interp:
            add(f"<p><b>{e(interp['verdict'])}</b></p>")
        add(_table(["axis", "reference median", "incoming median", "KS q", "PSI", "Cliff's δ", "magnitude"],
                   [[a["axis"], f"{a['reference_median']:.4g}", f"{a['incoming_median']:.4g}", f"{a['q']:.2g}",
                     f"{a['psi']:.3f}", f"{a['cliffs_delta']:+.3f}", a["magnitude"]] for a in cov["axes"]]))
    else:
        add("<p class='small'>No operational data were assessed.</p>")

    # 10 coverage
    cv = result.coverage
    add(f"<h2>10 · Coverage</h2><p>{cv.assessed} assessed · {cv.partial} partially assessed · {cv.not_assessed} not "
        f"assessed · {cv.failed} failed to execute · {cv.unsupported} unsupported, of {cv.total} attack classes. "
        "Coverage is computed from detector declarations and executions; it is not a security score.</p>")
    add(_table(["attack class", "layer", "state", "detectors", "reason", "required access"],
               [[r.attack_class, r.layer.value, badge(r.state), ", ".join(r.detectors), e(r.reason),
                 ", ".join(c.value for c in r.required_access)] for r in cv.rows], raw_cols={2, 4}))

    # 11 unsupported / not assessed
    add("<h2>11 · Unsupported and unassessed attack classes</h2>")
    gaps = [r for r in cv.rows if r.state in (CoverageState.UNSUPPORTED, CoverageState.NOT_ASSESSED,
                                             CoverageState.FAILED_TO_EXECUTE)]
    add(_table(["attack class", "state", "reason", "recommended additional evidence"],
               [[f"{r.title} ({r.attack_class})", badge(r.state), e(r.reason), e("; ".join(r.recommended_evidence))]
                for r in gaps], raw_cols={1, 2, 3}))

    # 12 limitations
    add("<h2>12 · Known limitations</h2>")
    lims: dict[str, list[str]] = {}
    for f in result.findings:
        lims.setdefault(f.detector_id, f.limitations)
    for det, items in lims.items():
        add(f"<h3><code>{e(det)}</code></h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>")

    # 13-15
    rep = result.reproduction
    add("<h2>13 · Reproduction metadata</h2>")
    if rep:
        add(_table(["field", "value"], [["seed", rep.seed], ["profile", f"{rep.profile} ({rep.profile_digest})"],
                                        ["git commit", rep.git_commit or "not a checkout"], ["encoder", rep.encoder],
                                        ["runtime settings", rep.runtime_settings], ["scan time", rep.scan_time],
                                        ["determinism", rep.determinism_note]]))
        add("<h2>14 · Tool and software versions</h2>")
        add(_table(["component", "version"], [["visionsentinel", __version__], ["python", rep.python],
                                              ["platform", rep.platform], *[[k, v] for k, v in rep.libraries.items()]]))
    add("<h2>15 · Cryptographic report digest</h2>")
    add(f"<p>Scan result digest (SHA-256 of the canonical result): <span class='mono'>{e(result.report_digest)}</span></p>")
    if manifest_note:
        add(f"<p>{e(manifest_note)}</p>")
    add(f"</main><footer>Generated by VisionSentinel {e(__version__)} · every assessment statement is qualified by "
        f"sections 3, 10, 11 and 12 · {sum(1 for _ in ATTACK_CLASSES)} attack classes in the catalogue.</footer></body></html>")
    return "".join(parts)
