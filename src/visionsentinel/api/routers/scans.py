"""Scan orchestration endpoints: creation, listing, real-time SSE event stream, findings, coverage, graph and comparison."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, func, select

from ...contracts import Layer, Role, ScanEvent as ScanEventContract, ScanResult, ScanStatus
from ...engine.request import ScanRequest
from ...engine.registry import default_registry
from ...provenance.keys import public_bytes
from ...reporting import verify_manifest
from ...reporting.compare import compare_scans
from ...storage import Scan, ScanEvent
from ..assets import AssetCompatibilityError, AssetNotFoundError, AssetResolver, AssetUnavailableError
from ..deps import Principal, get_state, mutation, require
from ..state import AppState

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scans", tags=["scans"])
SCAN_EVENTS_POLL_INTERVAL_SECONDS = 0.5
SCAN_EVENT_NAME = "scan_event"
SCAN_COMPLETE_EVENT_NAME = "scan_complete"
SCAN_UNAVAILABLE_CODE = "scan_unavailable"
SCAN_UNAVAILABLE_EVENT_NAME = SCAN_UNAVAILABLE_CODE


def is_terminal_scan_status(value: str | ScanStatus) -> bool:
    """Use the authoritative lifecycle enum when deciding whether a scan is done."""
    try:
        return ScanStatus(value).terminal
    except ValueError:
        return False


def _layer_results(result: ScanResult, layer: Layer) -> list[dict[str, Any]]:
    """Serialize every registered detector in a layer with its execution and section state."""
    executions = {execution.detector_id: execution for execution in result.executions}
    return [
        {
            "detector_id": spec.id,
            "title": spec.title,
            "execution": executions[spec.id].model_dump(mode="json") if spec.id in executions else None,
            "section": result.sections.get(spec.id),
        }
        for spec in default_registry().specs()
        if spec.layer == layer
    ]


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


class ReportVerifyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_digest: str | None = Field(default=None, max_length=80)


class ScanCompletePayload(BaseModel):
    scan_id: str
    status: ScanStatus


class ScanStreamUnavailablePayload(BaseModel):
    scan_id: str
    code: Literal["scan_unavailable"] = SCAN_UNAVAILABLE_CODE
    message: str = "The scan is no longer available; the event stream has ended."


def _result_or_error(scan_id: str, state: AppState) -> ScanResult:
    result = state.result(scan_id)
    if result is not None:
        return result
    with state.db.session() as session:
        if session.get(Scan, scan_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} not found")
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {scan_id!r} results not ready")


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
    principal: Principal = Depends(mutation(Role.ANALYST, allow_direct_demo=True)),
    state: AppState = Depends(get_state),
) -> dict:
    # The web boundary accepts workspace asset identifiers only. Permitting arbitrary
    # server paths here would turn an analyst session into a filesystem oracle.
    asset_request = ScanRequest(**body.model_dump())
    try:
        resolved_paths = AssetResolver(state.db, state.workspace).resolve_request(asset_request)
    except AssetNotFoundError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except AssetCompatibilityError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except AssetUnavailableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

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

    try:
        last_seq = max(0, int(request.headers.get("last-event-id", "0").strip()))
    except (AttributeError, ValueError, TypeError):
        last_seq = 0

    async def event_generator():
        nonlocal last_seq
        stream_ended = False

        async def disconnected() -> bool:
            return await request.is_disconnected()

        async def unavailable() -> str:
            nonlocal stream_ended
            stream_ended = True
            payload = ScanStreamUnavailablePayload(scan_id=scan_id).model_dump_json()
            return f"event: {SCAN_UNAVAILABLE_EVENT_NAME}\ndata: {payload}\n\n"

        while True:
            if await disconnected():
                break
            try:
                with state.db.session() as s:
                    events = (
                        s.query(ScanEvent)
                        .filter(ScanEvent.scan_id == scan_id, ScanEvent.seq > last_seq)
                        .order_by(ScanEvent.seq.asc())
                        .all()
                    )
                    max_seq = s.query(func.max(ScanEvent.seq)).filter(ScanEvent.scan_id == scan_id).scalar() or 0

                for ev in events:
                    if await disconnected():
                        return
                    last_seq = ev.seq
                    data = ScanEventContract(seq=ev.seq, t_ms=ev.t_ms, level=ev.level,
                                             message=ev.message, detector_id=ev.detector_id).model_dump_json()
                    yield f"id: {ev.seq}\nevent: {SCAN_EVENT_NAME}\ndata: {data}\n\n"

                if await disconnected():
                    return

                with state.db.session() as s:
                    current_scan = s.get(Scan, scan_id)

                if current_scan is None:
                    if not stream_ended:
                        yield await unavailable()
                    return

                if is_terminal_scan_status(current_scan.status):
                    terminal_event_id = max_seq + 1
                    if last_seq < terminal_event_id and not stream_ended:
                        final_data = ScanCompletePayload(
                            scan_id=scan_id, status=ScanStatus(current_scan.status)
                        ).model_dump_json()
                        yield f"id: {terminal_event_id}\nevent: {SCAN_COMPLETE_EVENT_NAME}\ndata: {final_data}\n\n"
                    return

                await asyncio.sleep(SCAN_EVENTS_POLL_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("scan event stream failed for scan %s", scan_id)
                if not stream_ended and not await disconnected():
                    yield await unavailable()
                return

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
    res = _result_or_error(scan_id, state)
    return res.coverage.model_dump(mode="json")


@router.get("/{scan_id}/contributors", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_contributors(scan_id: str, state: AppState = Depends(get_state)) -> dict:
    res = _result_or_error(scan_id, state)
    return {"scan_id": res.scan_id, "total": len(res.contributors),
            "contributors": [contributor.model_dump(mode="json") for contributor in res.contributors]}


@router.get("/{scan_id}/drift", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_drift(scan_id: str, state: AppState = Depends(get_state)) -> dict:
    res = _result_or_error(scan_id, state)
    return {"scan_id": res.scan_id, "layer": Layer.DRIFT.value, "detectors": _layer_results(res, Layer.DRIFT)}


@router.get("/{scan_id}/provenance", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_provenance(scan_id: str, state: AppState = Depends(get_state)) -> dict:
    res = _result_or_error(scan_id, state)
    return {"scan_id": res.scan_id, "layer": Layer.PROVENANCE.value,
            "detectors": _layer_results(res, Layer.PROVENANCE)}


@router.get("/{scan_id}/graph", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_graph(scan_id: str, state: AppState = Depends(get_state)) -> dict:
    res = _result_or_error(scan_id, state)
    if res.graph:
        return res.graph.model_dump(mode="json")
    return {"nodes": [], "edges": []}


@router.get("/{scan_id}/report.json", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_report_json(scan_id: str, state: AppState = Depends(get_state)) -> FileResponse:
    """Download the exact report bytes covered by the signed manifest."""
    with state.db.session() as s:
        scan = s.get(Scan, scan_id)
        path = Path(scan.report_dir) / "report.json" if scan and scan.report_dir else None
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"signed report for {scan_id!r} is not available")
    return FileResponse(path, media_type="application/json", filename=f"report_{scan_id}.json")


@router.get("/{scan_id}/report.html", dependencies=[Depends(require(Role.VIEWER))])
def get_scan_report_html(scan_id: str, state: AppState = Depends(get_state)) -> HTMLResponse:
    with state.db.session() as s:
        scan = s.get(Scan, scan_id)
        if scan and scan.report_dir:
            html_path = Path(scan.report_dir) / "report.html"
            if html_path.is_file():
                return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"HTML report for {scan_id!r} not found on disk")


@router.get("/{scan_id}/bundle/{artifact}", dependencies=[Depends(require(Role.VIEWER))])
def download_report_artifact(scan_id: str, artifact: str, state: AppState = Depends(get_state)) -> FileResponse:
    allowed = {"report.json", "report.html", "coverage.md", "manifest.json"}
    if artifact not in allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown report artifact")
    with state.db.session() as s:
        scan = s.get(Scan, scan_id)
        path = Path(scan.report_dir) / artifact if scan and scan.report_dir else None
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{artifact} for {scan_id!r} is not available")
    media = "text/html" if artifact.endswith(".html") else ("text/markdown" if artifact.endswith(".md") else "application/json")
    return FileResponse(path, media_type=media, filename=f"{scan_id}-{artifact}")


@router.post("/{scan_id}/report/verify", dependencies=[Depends(require(Role.VIEWER))])
def verify_scan_report(scan_id: str, body: ReportVerifyBody, state: AppState = Depends(get_state)) -> dict:
    with state.db.session() as s:
        scan = s.get(Scan, scan_id)
        report_dir = Path(scan.report_dir) if scan and scan.report_dir else None
        stored_digest = scan.report_digest if scan else None
    if report_dir is None or not report_dir.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"report for {scan_id!r} is not available")
    problems = verify_manifest(report_dir, public_bytes(state.keys.report))
    digest_matches = body.expected_digest is None or body.expected_digest == stored_digest
    return {"scan_id": scan_id, "report_digest": stored_digest, "expected_digest": body.expected_digest,
            "digest_matches": digest_matches, "manifest_intact": not problems, "problems": problems,
            "verified": not problems and digest_matches}


@router.post("/compare", dependencies=[Depends(require(Role.VIEWER))])
def compare_two_scans(body: CompareBody, state: AppState = Depends(get_state)) -> dict:
    res_a = state.result(body.scan_a)
    res_b = state.result(body.scan_b)
    if res_a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {body.scan_a!r} result not found")
    if res_b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scan {body.scan_b!r} result not found")

    return compare_scans(res_a, res_b)
