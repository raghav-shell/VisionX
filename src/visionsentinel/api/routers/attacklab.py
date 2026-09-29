"""Attack Lab endpoints: scenario catalog and controlled adversarial simulation executions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from ...attacklab.runner import list_scenarios, load_scenario, run_scenario
from ...contracts import Role
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


@router.post("/scenarios/{scenario_id}/run", status_code=status.HTTP_200_OK)
def run_scenario_endpoint(
    scenario_id: str,
    body: ScenarioRunBody,
    principal: Principal = Depends(mutation(Role.ANALYST)),
    state: AppState = Depends(get_state),
) -> dict:
    try:
        manifest = load_scenario(scenario_id)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"scenario {scenario_id!r} not found")

    result = run_scenario(manifest, workspace=state.workspace, profile=body.profile)
    if result.scan_result is not None:
        index_result(state, result.scan_result, report_dir=None)

    state.audit.record(
        principal.username,
        "run_attack_scenario",
        scenario_id,
        extra={"scan_id": result.scan_id, "detected": result.detected_expected_signals},
    )
    return result.to_dict()
