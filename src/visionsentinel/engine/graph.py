"""Evidence graph for one scan: Contributor → Sample → Detector → Finding → Evidence (→ Class / Model / Record)."""

from __future__ import annotations

from ..contracts import AssetType, EvidenceGraph, ScanResult
from ..evidence.graph import GraphBuilder

MAX_SAMPLES_PER_FINDING = 40

_ASSET_NODE = {AssetType.MODEL: "Model", AssetType.REFERENCE_MODEL: "Model", AssetType.INFERENCE_LEDGER: "Asset",
               AssetType.TRUST_ROOT: "Asset"}


def build_graph(result: ScanResult) -> EvidenceGraph:
    g = GraphBuilder(max_nodes=6000)
    for a in result.assets:
        g.node(f"asset:{a.role.value}:{a.asset_id}", _ASSET_NODE.get(a.role, "Dataset"), a.name, role=a.role.value,
               digest=a.digest, format=a.format)
    for c in result.contributors:
        g.node(f"contributor:{c.contributor}", "Contributor", c.contributor, risk_tier=c.risk_tier,
               posterior_anomaly=c.posterior_anomaly, samples=c.samples, flagged=c.flagged)
    for e in result.executions:
        g.node(f"detector:{e.detector_id}", "Detector", e.title, state=e.state.value, mode=e.mode)
    dataset_asset = next((f"asset:{a.role.value}:{a.asset_id}" for a in result.assets if a.role == AssetType.DATASET), None)
    for f in result.findings:
        fid = f"finding:{f.id}"
        g.node(fid, "Finding", f.title, severity=f.severity.value, disposition=f.recommended_disposition.value,
               attack_class=f.attack_class, confidence=f.confidence)
        g.edge(fid, f"detector:{f.detector_id}", "GENERATED_BY")
        asset_key = next((f"asset:{a.role.value}:{a.asset_id}" for a in result.assets if a.asset_id == f.asset_id), None)
        if asset_key:
            g.edge(fid, asset_key, "ABOUT")
        for c in f.affected_contributors:
            g.edge(fid, f"contributor:{c}", "ABOUT")
        for ev in f.evidence:
            eid = f"evidence:{ev.id}"
            g.node(eid, "Evidence", ev.title, kind=ev.kind.value, digest=ev.blob.digest if ev.blob else None)
            g.edge(fid, eid, "SUPPORTED_BY")
        for s in f.affected_samples[:MAX_SAMPLES_PER_FINDING]:
            sid = f"sample:{s.sample_id}"
            g.node(sid, "Sample", s.sample_id, declared_label=s.label, contributor=s.contributor)
            g.edge(fid, sid, "ABOUT")
            g.edge(sid, f"detector:{f.detector_id}", "FLAGGED_BY")
            if s.contributor:
                g.edge(sid, f"contributor:{s.contributor}", "SUPPLIED_BY")
            if dataset_asset:
                g.edge(sid, dataset_asset, "DERIVED_FROM")
        target = f.tags.get("target_class")
        if target:
            cid = f"class:{target}"
            g.node(cid, "Class", target)
            g.edge(fid, cid, "CORRELATES_WITH")
    graph = g.build()
    return graph
