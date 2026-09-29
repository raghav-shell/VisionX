"""Scan orchestration endpoints: creation, listing, real-time SSE event stream, findings, coverage, graph and comparison."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from ...contracts import Disposition, Role, ScanResult, ScanStatus, Severity
from ...engine.request import ScanRequest
from ...reporting.compare import compare_scans
from ...storage import FindingState, Scan, ScanEvent
from ..deps import Principal, get_state, mutation, require
from ..state import AppState

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scans", tags=["scans"])


class ScanSubmitBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="assessment", max_length=120)
    profile: str = Field(default="baseline", max_length=64)
    dataset: str | None = None
    dataset_format: str = "auto"
    reference_dataset: str | None = None
    probe_dataset: str | None = None
    suspect_inputs: str | None = None
    operational_data: str | None = None
    model: str | None = None
    reference_model: str | None = None
    architecture: str | None = None
    preprocess: str | None = None
    reference_fingerprint: str | None = None
    ledger: str | None = None
    trust_root: str | None = None
    anchor: str | None = None
    inference_inputs: str | None = None


class CompareBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scan_a: str = Field(min_length=1, max_length=128)
    scan_b: str = Field(min_length=1, max_length=128)


def _scan_summary(scan: Scan) -> dict:
    return {
        "id": scan.id,
        "name": scan.name,
        "status": scan.status,
        "profile": scan.profile,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "overall_disposition": scan.overall_disposition,
        "findings_count": scan.findings,
        "critical_count": scan.critical,
        "quarantine_count": scan.quarantine,
        "review_count": scan.review,
        "coverage": {
            "assessed": scan.coverage_assessed,
            "partial": scan.coverage_partial,
            "total": scan.coverage_total,
            "pct": round((scan.coverage_assessed + 0.5 * scan.coverage_partial) / max(scan.coverage_total, 1) * 100, 1),
        },
        "report_digest": scan.report_digest,
        "created_by": scan.created_by,
    }


@router.get("", dependencies=[Depends(require(Role.VIEWER))])
def list_scans(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    state: AppState = Depends(get_state),
) -> dict:
    with state.db.session() as s:
        q = select(Scan).order_by(desc(Scan.created_at))
        if status_filter:
            q = q.filter(Scan.status == status_filter.upper())
        total = s.query(Scan).count()
        rows = s.scalars(q.offset(offset).limit(limit)).all()
        return {"total": total, "scans": [_scan_summary(r) for r in rows]}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def submit_scan(
    body: ScanSubmitBody,
    principal: Principal = Depends(mutation(Role.ANALYST)),
    state: AppState = Depends(get_state),
) -> dict:
    # The web boundary accepts workspace asset identifiers only. Permitting arbitrary
    # server paths here would turn an analyst session into a filesystem oracle.
    req_dict = body.model_dump()
    resolved_paths: dict[str, Path] = {}
    with state.db.session() as s:
        from ...storage import Asset

        for field_name in (
            "dataset", "reference_dataset", "probe_dataset", "suspect_inputs", "operational_data",
            "model", "reference_model", "preprocess", "reference_fingerprint", "ledger",
            "trust_root", "anchor", "inference_inputs",
        ):
            val = req_dict.get(field_name)
            if val:
                asset = s.get(Asset, val)
                if asset is None:
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                        f"{field_name} must be an imported asset identifier")
                if (asset.details or {}).get("lifecycle", "ACTIVE") != "ACTIVE":
                    raise HTTPException(status.HTTP_409_CONFLICT,
                                        f"{field_name} references archived asset {val!r}; restore it before scanning")
                resolved_paths[field_name] = Path(asset.path)

    scan_req = ScanRequest(
        name=body.name,
        profile=body.profile,
        dataset_format=body.dataset_format,
        architecture=body.architecture,
        **resolved_paths,
    )

    if not scan_req.supplied():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "at least one asset must be supplied (e.g. dataset, model, ledger or operational_data)",
        )

    scan_id = state.runner.submit_scan(scan_req, principal.username)
    return {"scan_id": scan_id, "status": ScanStatus.PENDING.value, "name": body.name, "profile": body.profile}


@router.get("/{scan_id}", dependencies=[Depends(require(Role.VIEWER))])
def get_scan(scan_id: str, state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as s:
        scan = s.get(Scan, scan_id)
        if scan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} not found")
        summary = _scan_summary(scan)
        res = state.result(scan_id)
        if res is not None:
            summary["assets"] = [a.model_dump(mode="json") for a in res.assets]
            summary["capabilities"] = [c.model_dump(mode="json") for c in res.capabilities]
            summary["reproduction"] = res.reproduction.model_dump(mode="json") if res.reproduction else None
            summary["sections_available"] = list(res.sections.keys())
        return summary


@router.get("/{scan_id}/events", dependencies=[Depends(require(Role.VIEWER))])
async def scan_events_stream(scan_id: str, request: Request, state: AppState = Depends(get_state)):
    """Server-Sent Events endpoint streaming live log events for the scan."""
    with state.db.session() as s:
        scan = s.get(Scan, scan_id)
        if scan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} not found")

    async def event_generator():
        last_seq = 0
        terminal_statuses = {ScanStatus.COMPLETED.value, ScanStatus.COMPLETED_WITH_FINDINGS.value,
                             ScanStatus.FAILED.value, ScanStatus.ERROR.value}
        while True:
            if await request.is_disconnected():
                break

            with state.db.session() as s:
                events = (
                    s.query(ScanEvent)
                    .filter(ScanEvent.scan_id == scan_id, ScanEvent.seq > last_seq)
                    .order_by(ScanEvent.seq.asc())
                    .all()
                )
                current_scan = s.get(Scan, scan_id)
                current_status = current_scan.status if current_scan else None

            for ev in events:
                last_seq = ev.seq
                data = json.dumps({
                    "seq": ev.seq,
                    "t_ms": ev.t_ms,
                    "level": ev.level,
                    "message": ev.message,
                    "stage": ev.stage,
                    "detector": ev.detector,
                })
                yield f"event: scan_event\ndata: {data}\n\n"

            if current_status in terminal_statuses:
                final_data = json.dumps({"status": current_status, "scan_id": scan_id})
                yield f"event: scan_complete\ndata: {final_data}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/{scan_id}/plan", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_plan(scan_id: str, state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as s:
        scan = s.get(Scan, scan_id)
        if scan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} not found")
        if scan.plan and "plan" in scan.plan:
            return {"plan": scan.plan["plan"]}
    res = state.result(scan_id)
    if res is None:
        return {"plan": []}
    return {"plan": [n.model_dump(mode="json") for n in res.plan]}


@router.get("/{scan_id}/findings", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_findings(
    scan_id: str,
    severity: str | None = None,
    disposition: str | None = None,
    layer: str | None = None,
    attack_class: str | None = None,
    state: AppState = Depends(get_state),
) -> dict:
    res = state.result(scan_id)
    if res is None:
        # Check DB states
        with state.db.session() as s:
            if s.get(Scan, scan_id) is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} not found")
        return {"findings": [], "total": 0}

    findings = res.findings
    if severity:
        findings = [f for f in findings if f.severity.value == severity.upper()]
    if disposition:
        findings = [f for f in findings if f.recommended_disposition.value == disposition.upper()]
    if layer:
        findings = [f for f in findings if f.layer.value == layer.lower()]
    if attack_class:
        findings = [f for f in findings if f.attack_class == attack_class]

    return {
        "scan_id": scan_id,
        "total": len(findings),
        "findings": [f.model_dump(mode="json") for f in findings],
    }


@router.get("/{scan_id}/coverage", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_coverage(scan_id: str, state: AppState = Depends(get_state)) -> dict:
    res = state.result(scan_id)
    if res is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} results not ready")
    return res.coverage.model_dump(mode="json")


@router.get("/{scan_id}/contributors", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_contributors(scan_id: str, state: AppState = Depends(get_state)) -> dict:
    res = state.result(scan_id)
    if res is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} results not ready")
    contribs = res.sections.get("data.contributors") or {}
    return contribs


@router.get("/{scan_id}/drift", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_drift(scan_id: str, state: AppState = Depends(get_state)) -> dict:
    res = state.result(scan_id)
    if res is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} results not ready")
    cov = res.sections.get("drift.covariate") or {}
    sem = res.sections.get("drift.semantic") or {}
    res_drift = res.sections.get("drift.reasoning") or {}
    return {"covariate": cov, "semantic": sem, "reasoning": res_drift}


@router.get("/{scan_id}/provenance", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_provenance(scan_id: str, state: AppState = Depends(get_state)) -> dict:
    res = state.result(scan_id)
    if res is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} results not ready")
    prov = res.sections.get("provenance.ledger") or {}
    return prov


@router.get("/{scan_id}/graph", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_graph(scan_id: str, state: AppState = Depends(get_state)) -> dict:
    res = state.result(scan_id)
    if res is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} results not ready")
    if res.graph:
        return res.graph.model_dump(mode="json")
    return {"nodes": [], "edges": []}


@router.get("/{scan_id}/report.json", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_report_json(scan_id: str, state: AppState = Depends(get_state)) -> Response:
    res = state.result(scan_id)
    if res is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} report not available")
    return Response(
        content=res.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="report_{scan_id}.json"'},
    )


@router.get("/{scan_id}/report.html", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_report_html(scan_id: str, state: AppState = Depends(get_state)) -> HTMLResponse:
    with state.db.session() as s:
        scan = s.get(Scan, scan_id)
        if scan and scan.report_dir:
            html_path = Path(scan.report_dir) / "report.html"
            if html_path.is_file():
                return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"HTML report for {scan_id!r} not found on disk")


@router.post("/compare", dependencies=[Depends(require(Role.VIEWER))])
def compare_two_scans(body: CompareBody, state: AppState = Depends(get_state)) -> dict:
    res_a = state.result(body.scan_a)
    res_b = state.result(body.scan_b)
    if res_a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {body.scan_a!r} result not found")
    if res_b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {body.scan_b!r} result not found")

    return compare_scans(res_a, res_b)
