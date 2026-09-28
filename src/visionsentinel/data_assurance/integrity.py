"""Dataset manifest integrity: every listed file exists, decodes, is confined, and matches its declaration."""

from __future__ import annotations

from ..contracts import (
    AssetType,
    AttackSupport,
    CalibrationRequirement,
    DetectorMode,
    DetectorSpec,
    EvidenceKind,
    Layer,
    ProposedFinding,
    RuntimeClass,
    Severity,
    SupportLevel,
)
from ..core.context import DetectorContext
from ..core.detector import Detector, DetectorResult, PlanContext, SampleFlag
from .common import DATA_ASSUMPTIONS, dataset, join_ids, ref, table_evidence


def _norm_digest(d: str | None) -> str | None:
    if not d:
        return None
    d = d.strip().lower()
    return d if d.startswith("sha256:") else f"sha256:{d}"


class ManifestIntegrity(Detector):
    spec = DetectorSpec(
        id="data.manifest_integrity", version="1.0.0", title="Dataset manifest integrity", layer=Layer.DATA,
        summary="Verifies that every listed sample exists, decodes, stays inside the dataset root and matches any "
                "SHA-256 and dimensions declared by the contributor.",
        modes=[DetectorMode(name="deterministic", description="file-level verification of every sample")],
        supports=[AttackSupport(attack_class="corrupted_samples", level=SupportLevel.FULL)],
        runtime=RuntimeClass.FAST, evidence_kinds=[EvidenceKind.HASH_LIST, EvidenceKind.TABLE],
        limitations=["Detects substitution only where the manifest declares a digest; an attacker who controls the "
                     "manifest can re-declare digests.",
                     "Decodability is checked, visual plausibility is not (see OOD and trigger analysis)."],
        access_assumptions=DATA_ASSUMPTIONS, deterministic=True, calibration=CalibrationRequirement.NOT_APPLICABLE,
    )

    def preconditions(self, caps, plan: PlanContext) -> list[str]:
        return [] if plan.fact("dataset.present") else ["no dataset asset was supplied"]

    def run(self, ctx: DetectorContext) -> DetectorResult:
        ds = dataset(ctx)
        unsafe = [s for s in ds.samples if s.error_kind == "unsafe"]
        unreadable = [s for s in ds.samples if s.error_kind == "unreadable"]
        mismatched = [s for s in ds.samples if s.digest and s.declared_digest
                      and _norm_digest(s.declared_digest) != s.digest]
        dims = [s for s in ds.samples if s.width and s.declared_width and s.declared_height
                and (s.width, s.height) != (s.declared_width, s.declared_height)]
        declared = sum(1 for s in ds.samples if s.declared_digest)
        res = DetectorResult(samples_processed=len(ds.samples), metrics={
            "samples": len(ds.samples), "readable": len(ds.readable), "declared_digests": declared,
            "digest_mismatches": len(mismatched), "unreadable": len(unreadable), "unsafe": len(unsafe),
            "dimension_mismatches": len(dims)})

        def emit(group, severity, title, reason, kind_note, columns, rows):
            ev = table_evidence(ctx, title, reason, columns, rows, kind=EvidenceKind.HASH_LIST)
            contribs = sorted({s.contributor for s in group if s.contributor})
            res.findings.append(ProposedFinding(
                attack_class="corrupted_samples", asset_type=AssetType.DATASET, asset_id=ds.name,
                subject=f"integrity:{kind_note}", title=title, reason=reason, severity=severity, confidence=1.0,
                evidence=[ev], access_assumptions=DATA_ASSUMPTIONS, limitations=self.spec.limitations,
                affected_samples=[ref(s, kind_note) for s in group[:200]], affected_count=len(group),
                affected_contributors=contribs, deterministic=True, calibrated=True,
                recommended_action="Obtain the original files from the contributor and re-verify before use."))
            for s in group:
                res.flags.append(SampleFlag(s.id, s.contributor, "corrupted_samples", self.spec.id, 1.0, severity,
                                            s.batch))

        if mismatched:
            emit(mismatched, Severity.HIGH, f"{len(mismatched)} sample file(s) do not match their declared SHA-256",
                 f"{len(mismatched)} of {declared} samples with a declared digest now hash to a different value "
                 f"({join_ids([s.id for s in mismatched])}); the files were altered after the manifest was written.",
                 "digest-mismatch", ["sample", "contributor", "declared", "observed"],
                 [[s.id, s.contributor, _norm_digest(s.declared_digest), s.digest] for s in mismatched])
        if unsafe:
            emit(unsafe, Severity.HIGH, f"{len(unsafe)} sample path(s) rejected by the file-system boundary",
                 f"{len(unsafe)} listed samples resolve outside the dataset root or are not regular files "
                 f"({join_ids([s.id for s in unsafe])}); they were not read.", "unsafe-path",
                 ["sample", "contributor", "reason"], [[s.id, s.contributor, s.error] for s in unsafe])
        if unreadable:
            emit(unreadable, Severity.MEDIUM, f"{len(unreadable)} sample file(s) missing or undecodable",
                 f"{len(unreadable)} of {len(ds.samples)} listed samples are missing, truncated or not decodable "
                 f"images ({join_ids([s.id for s in unreadable])}).", "unreadable",
                 ["sample", "contributor", "error"], [[s.id, s.contributor, s.error] for s in unreadable])
        if dims:
            emit(dims, Severity.LOW, f"{len(dims)} sample(s) differ from their declared dimensions",
                 f"{len(dims)} samples decode to dimensions different from those declared in the annotations "
                 f"({join_ids([s.id for s in dims])}).", "dimension-mismatch",
                 ["sample", "declared", "observed"],
                 [[s.id, f"{s.declared_width}x{s.declared_height}", f"{s.width}x{s.height}"] for s in dims])
        return res
