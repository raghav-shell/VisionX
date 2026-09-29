"""Drift & Distribution Shift analysis endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ...contracts import Role
from ...engine.request import ScanRequest
from ...engine.scan import run_scan
from ...storage import Asset
from ..deps import Principal, get_state, mutation, require
from ..state import AppState

router = APIRouter(prefix="/api/drift", tags=["drift"])


class DriftAnalyzeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference_dataset: str | None = None
    incoming_data: str = Field(min_length=1)
    model: str | None = None
    profile: str = Field(default="baseline")


@router.post("/analyze")
def analyze_drift(
    body: DriftAnalyzeBody,
    principal: Principal = Depends(mutation(Role.ANALYST)),
    state: AppState = Depends(get_state),
) -> dict:
    ref_path: Path | None = None
    inc_path: Path | None = None
    model_path: Path | None = None

    with state.db.session() as s:
        if body.reference_dataset:
            a = s.get(Asset, body.reference_dataset)
            if a is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                    "reference_dataset must be an imported asset identifier")
            ref_path = Path(a.path)
        a = s.get(Asset, body.incoming_data)
        if a is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "incoming_data must be an imported asset identifier")
        inc_path = Path(a.path)
        if body.model:
            a = s.get(Asset, body.model)
            if a is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                    "model must be an imported asset identifier")
            model_path = Path(a.path)

    if not inc_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "incoming operational data asset is unavailable")

    req = ScanRequest(
        name="on-demand drift assessment",
        profile=body.profile,
        reference_dataset=ref_path,
        operational_data=inc_path,
        model=model_path,
    )

    result = run_scan(req, workspace=state.workspace)

    cov = result.sections.get("drift.covariate", {}).get("covariate", {})
    sem = result.sections.get("drift.semantic", {}).get("semantic", {})
    reasoning = result.sections.get("drift.reasoning", {}).get("drift_reasoning", {})

    findings = [f.model_dump(mode="json") for f in result.findings if f.layer.value == "drift"]

    return {
        "scan_id": result.scan_id,
        "covariate": cov,
        "semantic": sem,
        "reasoning": reasoning,
        "findings": findings,
        "overall_disposition": result.summary.overall_disposition.value if result.summary else "REVIEW",
    }
