"""Attack Lab endpoints: scenario catalog and controlled adversarial simulation executions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ...attacklab.runner import list_scenarios, load_scenario, run_scenario
from ...contracts import JobKind, JobStatus, Role
from ...reporting import write_report
from ..deps import Principal, get_state, mutation, require
from ..runner import index_result
from ..state import AppState

router = APIRouter(prefix="/api/attacklab", tags=["attacklab"])


class ScenarioRunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: str = Field(default="selftest")


@router.get("/scenarios", dependencies=[Depends(require(Role.VIEWER))])
def get_scenarios() -> dict:
    scenarios = list_scenarios()
    return {
        "total": len(scenarios),
        "scenarios": [s.model_dump() for s in scenarios],
    }


@router.get("/scenarios/{scenario_id}", dependencies=[Depends(require(Role.VIEWER))])
def get_scenario(scenario_id: str) -> dict:
    try:
        manifest = load_scenario(scenario_id)
        return manifest.model_dump()
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scenario {scenario_id!r} not found")


@router.post("/scenarios/{scenario_id}/run", status_code=status.HTTP_202_ACCEPTED)
def run_scenario_endpoint(
    scenario_id: str,
    body: ScenarioRunBody,
    principal: Principal = Depends(mutation(Role.ANALYST, allow_direct_demo=True)),
    state: AppState = Depends(get_state),
) -> dict:
    try:
        manifest = load_scenario(scenario_id)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scenario {scenario_id!r} not found")

    def execute(ctx):
        ctx.step("scenario validated", scenario_id)
        scenario = load_scenario(scenario_id)
        result = run_scenario(scenario, workspace=state.workspace, profile=body.profile)
        if result.scan_result is not None:
            paths = write_report(result.scan_result, state.workspace.reports, state.store, state.keys.report)
            index_result(state, result.scan_result, report_dir=str(paths["report.json"].parent))
            ctx.link_scan(result.scan_result.scan_id)
        ctx.step("scenario evaluated", result.scan_id)
        return result.to_dict()

    job_id = state.runner.submit_job(JobKind.ATTACK_LAB.value, scenario_id, principal.username, execute)
    return {"job_id": job_id, "status": JobStatus.QUEUED.value, "kind": JobKind.ATTACK_LAB.value,
            "subject": scenario_id}
