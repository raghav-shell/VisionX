"""The assurance scan pipeline.

    assets → capability probe → access policy → encoder → plan (every detector) → execute
           → policy decisions → contributor assessment → coverage → evidence graph → sealed result
"""

from __future__ import annotations

import logging
import secrets
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone

from .. import __version__
from ..contracts import (
    Availability,
    Disposition,
    ExecutionState,
    ReproductionInfo,
    ScanEvent,
    ScanResult,
    ScanStatus,
    ScanSummary,
    Severity,
)
from ..core.capabilities import CapabilitySet
from ..core.context import DetectorContext
from ..core.detector import PlanContext
from ..core.determinism import DETERMINISM_NOTE, git_commit, library_versions, platform_info, seed_everything
from ..core.events import EventLog
from ..core.executor import execute_plan
from ..core.hashing import digest_json
from ..core.planner import build_plan, plan_counts
from ..core.profiles import load_profile
from ..core.registry import DetectorRegistry
from ..core.workspace import Workspace
from ..evidence.store import EvidenceStore
from ..risk.coverage import compute_coverage
from ..risk.policy import PolicyEngine
from .assets import PreparedAssets, build_analyses, load_datasets
from .encoders import select_encoder
from .findings import finalize_findings
from .registry import default_registry
from .request import ScanRequest

log = logging.getLogger(__name__)

# Hooks let later layers (model, provenance, drift, contributor risk, graph) join the pipeline without
# this module growing a dependency on every one of them at import time.
AssetHook = Callable[[ScanRequest, "object", PreparedAssets, EventLog, Workspace], None]
ASSET_HOOKS: list[AssetHook] = []
POST_HOOKS: list[Callable[[ScanResult, dict, PreparedAssets, "object"], None]] = []


def new_scan_id(now: datetime) -> str:
    return f"SCN-{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2).upper()}"


def run_scan(request: ScanRequest, *, workspace: Workspace | None = None, registry: DetectorRegistry | None = None,
             on_event: Callable[[ScanEvent], None] | None = None, scan_time: datetime | None = None,
             on_plan: Callable[[ScanResult], None] | None = None) -> ScanResult:
    workspace = (workspace or Workspace.default()).ensure()
    registry = registry or default_registry()
    now = scan_time or datetime.now(timezone.utc)
    scan_id = request.scan_id or new_scan_id(now)
    events = EventLog(on_event)
    profile = load_profile(request.profile, registry)
    events.stage(f"scan {scan_id} opened · profile '{profile.name}' ({profile.budget.value}) · digest {profile.digest[7:19]}")
    runtime_settings = seed_everything(profile.seed, torch_threads=profile.analysis.torch_threads)
    store = EvidenceStore(workspace.evidence)

    prepared = PreparedAssets()
    try:
        events.stage("probing supplied assets")
        load_datasets(request, profile, prepared, events)
        for hook in ASSET_HOOKS:
            hook(request, profile, prepared, events, workspace)
        select_encoder(prepared, profile)
        for note in prepared.encoder_notes:
            events.emit(note)
        build_analyses(prepared, profile, workspace, events)

        caps = CapabilitySet.build(prepared.probed, profile.access.deny)
        for rec in caps.as_records():
            if rec.present:
                events.emit(f"capability {rec.capability.value:<22} {'WITHHELD' if rec.withheld else 'AVAILABLE'}")
        plan_ctx = PlanContext(budget=profile.budget, facts=prepared.facts)
        plan = build_plan(registry, caps, profile, plan_ctx)
        counts = plan_counts(plan)
        events.stage(f"{len(plan)} checks planned · {counts['READY']} full · {counts['DEGRADED']} degraded · "
                     f"{counts['UNAVAILABLE']} unavailable · {counts['BUDGET_EXCLUDED']} budget-excluded")

        result = ScanResult(scan_id=scan_id, name=request.name, status=ScanStatus.PLANNED, profile=profile.name,
                            budget=profile.budget, created_at=now, assets=prepared.descriptors,
                            capabilities=caps.as_records(), plan=[c.negotiation for c in plan], executions=[],
                            findings=[], coverage=compute_coverage(registry.specs(), [c.negotiation for c in plan], []))
        if on_plan:
            on_plan(result)

        shared: dict = {"scan_time": now}

        def make_context(check, upstream):
            return DetectorContext(scan_id=scan_id, spec=check.detector.spec, mode=check.negotiation.mode or "",
                                   params=check.params, calibration=check.calibration, profile=profile,
                                   capabilities=caps, assets=prepared.objects, blobs=store, seed=profile.seed,
                                   upstream=upstream, shared=shared,
                                   emit=lambda m, d=check.detector.spec.id: events.emit(m, detector_id=d))

        events.stage("executing detectors")
        executions, results = execute_plan(plan, make_context, events, track_memory=profile.analysis.track_memory)

        policy = PolicyEngine(profile.risk, profile.policy_digest)
        specs = {s.id: s for s in registry.specs()}
        negotiations = {c.negotiation.detector_id: c.negotiation for c in plan}
        findings = finalize_findings(scan_id, results, specs, negotiations, policy, now)
        coverage = compute_coverage(registry.specs(), list(negotiations.values()), executions)
        events.stage(f"{len(findings)} findings · coverage {coverage.assessed}/{coverage.total} assessed, "
                     f"{coverage.partial} partial")

        sections: dict = {"encoder": {"id": prepared.encoder.id if prepared.encoder else None,
                                      "semantic": bool(prepared.encoder and prepared.encoder.semantic),
                                      "notes": prepared.encoder_notes}}
        for det_id, r in results.items():
            if r.section:
                sections[det_id] = r.section
        if "dataset" in prepared.objects:
            sections["dataset"] = prepared.objects["dataset"].summary()

        result = result.model_copy(update=dict(status=ScanStatus.RUNNING, executions=executions, findings=findings,
                                               coverage=coverage, sections=sections))
        for hook in POST_HOOKS:
            hook(result, results, prepared, profile)

        py, plat = platform_info()
        result.summary = summarise(result)
        result.reproduction = ReproductionInfo(
            seed=profile.seed, profile=profile.name, profile_digest=profile.digest, software_version=__version__,
            git_commit=git_commit(), python=py, platform=plat, libraries=library_versions(),
            runtime_settings=runtime_settings, encoder=prepared.encoder.id if prepared.encoder else None,
            scan_time=now, determinism_note=DETERMINISM_NOTE)
        result.status = ScanStatus.SEALED
        result.completed_at = datetime.now(timezone.utc)
        events.stage(f"scan sealed · overall disposition {result.summary.overall_disposition.value}")
        result.events = events.events
        result.report_digest = digest_json(result.model_dump(mode="json", exclude={"report_digest", "events"}))
        return result
    finally:
        prepared.close()


def summarise(result: ScanResult) -> ScanSummary:
    by_sev = Counter(f.severity for f in result.findings)
    by_disp = Counter(f.recommended_disposition for f in result.findings)
    per_asset: dict[str, Disposition] = {}
    for f in result.findings:
        key = f"{f.asset_type.value}:{f.asset_id}"
        per_asset[key] = Disposition.max(per_asset.get(key, Disposition.ACCEPT), f.recommended_disposition)
    states = Counter(e.state for e in result.executions)
    planned = Counter(e.planned for e in result.executions)
    overall = Disposition.max(Disposition.ACCEPT, *by_disp.keys()) if by_disp else Disposition.ACCEPT
    return ScanSummary(
        findings=len(result.findings), by_severity={s: by_sev.get(s, 0) for s in Severity},
        by_disposition={d: by_disp.get(d, 0) for d in Disposition}, asset_dispositions=per_asset,
        coverage_assessed=result.coverage.assessed, coverage_partial=result.coverage.partial,
        coverage_total=result.coverage.total, detectors_completed=states.get(ExecutionState.COMPLETED, 0),
        detectors_degraded=states.get(ExecutionState.COMPLETED_DEGRADED, 0),
        detectors_unavailable=planned.get(Availability.UNAVAILABLE, 0),
        detectors_error=states.get(ExecutionState.ERROR, 0), detectors_abstained=states.get(ExecutionState.ABSTAINED, 0),
        detectors_budget_excluded=planned.get(Availability.BUDGET_EXCLUDED, 0), overall_disposition=overall)
