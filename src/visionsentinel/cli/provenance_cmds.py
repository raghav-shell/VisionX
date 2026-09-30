"""CLI commands for keys, trust roots, protected inference, verification, drift and fingerprints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..core.errors import VisionSentinelError


def _cmd_verify(args: argparse.Namespace) -> int:
    from ..provenance.verifier import main as verify_main

    ledger = args.ledger_opt or args.ledger
    if ledger is None:
        raise VisionSentinelError("no ledger given", hint="visionsentinel verify LEDGER --trust-root TRUST.json")
    argv = [str(ledger), "--trust-root", str(args.trust_root)]
    if args.anchor:
        argv += ["--anchor", str(args.anchor)]
    if args.inputs:
        argv += ["--inputs", str(args.inputs)]
    if args.json:
        argv.append("--json")
    return verify_main(argv)


def _cmd_keys(args: argparse.Namespace) -> int:
    from ..provenance.keys import generate_key, save_private_key, trust_entry

    if args.out.exists() and not args.force:
        raise VisionSentinelError(f"{args.out} exists", hint="use --force to overwrite")
    key = generate_key()
    save_private_key(key, args.out)
    print(json.dumps(trust_entry(key, args.roles.split(","), args.comment), indent=1))
    print(f"private key written to {args.out} (mode 0600)")
    return 0


def _cmd_trust_root(args: argparse.Namespace) -> int:
    from ..loaders.models import open_model
    from ..model_assurance.identity import architecture_digest
    from ..provenance.keys import load_private_key, trust_entry
    from ..provenance.trust import build_trust_root_document

    keys = [trust_entry(load_private_key(Path(k)), roles.split(","), Path(k).stem)
            for k, roles in (item.split(":", 1) if ":" in item else (item, "ledger,anchor") for item in args.key)]
    models = []
    for m in args.approve_model or []:
        h = open_model(Path(m))
        try:
            models.append({"name": Path(m).stem, "artifact_digest": h.artifact_digest, "param_digest": h.param_digest,
                           "preprocess_digest": h.cfg.digest, "architecture_digest": architecture_digest(h.graph()),
                           "approved_by": args.approver})
        finally:
            h.close()
    args.out.write_text(json.dumps(build_trust_root_document(args.name, keys, models), indent=1), encoding="utf-8")
    print(f"trust root written to {args.out}: {len(keys)} key(s), {len(models)} approved model(s)")
    return 0


def _cmd_infer(args: argparse.Namespace) -> int:
    from ..core.limits import ResourceLimits
    from ..loaders.images import IMAGE_SUFFIXES, decode_bytes
    from ..loaders.models import open_model
    from ..loaders.safe_io import read_bounded
    from ..provenance.inference import InferenceRecorder
    from ..provenance.keys import load_private_key
    from ..provenance.ledger import LedgerWriter

    limits = ResourceLimits()
    model = open_model(args.model, limits, preprocess_path=args.preprocess)
    try:
        writer = LedgerWriter(args.ledger, load_private_key(args.key), checkpoint_every=args.checkpoint_every,
                              anchor_path=args.anchor)
        rec = InferenceRecorder(model, writer)
        files = sorted(p for p in args.inputs.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES and p.is_file())
        for p in files:
            data = read_bounded(p, limits.max_file_bytes)
            r = rec.record(data, p.name, decode_bytes(data, p.name, limits))
            print(f"seq {r['seq']:5d}  {p.name:40s} → {r['body']['output']['label']}")
        writer.checkpoint()
    finally:
        model.close()
    print(f"{len(files)} protected inference record(s) appended to {args.ledger}")
    return 0


def _cmd_drift(args: argparse.Namespace) -> int:
    from ..core.workspace import Workspace
    from ..engine.request import ScanRequest
    from ..engine.scan import run_scan
    from .commands import write_outputs
    from .output import heading, state, table

    r = run_scan(ScanRequest(name="drift assessment", profile=args.profile, reference_dataset=args.reference,
                             operational_data=args.incoming, model=args.model), workspace=Workspace.default())
    cov = r.sections.get("drift.covariate", {}).get("covariate", {})
    if cov:
        print(heading("INTERPRETABLE AXES"))
        print(table([[a["axis"], f"{a['reference_median']:.4g}", f"{a['incoming_median']:.4g}", f"{a['q']:.2g}",
                      f"{a['cliffs_delta']:+.2f}", a["magnitude"]] for a in cov["axes"]],
                    ["AXIS", "REFERENCE", "INCOMING", "KS q", "CLIFF δ", "MAGNITUDE"]))
    for f in r.findings:
        if f.detector_id.startswith("drift"):
            print(f"\n{state(f.severity.value, 8)} {f.title}\n    {f.reason}")
    for p in write_outputs(r, args.out):
        print(f"\nwrote {p}")
    return 0


def _cmd_fingerprint(args: argparse.Namespace) -> int:
    import numpy as np

    from ..core.limits import ResourceLimits
    from ..loaders.datasets import open_dataset
    from ..loaders.models import open_model
    from ..model_assurance.behaviour import fingerprint_document
    from ..model_assurance.probes import battery

    model = open_model(args.model, ResourceLimits(), preprocess_path=args.preprocess)
    try:
        imgs = ids = None
        if args.probe:
            ds = open_dataset(args.probe)
            imgs = np.stack([ds.load(s, model.cfg.input_size) for s in ds.readable])
            ids = [s.id for s in ds.readable]
        doc = fingerprint_document(model, battery(model.cfg.input_size, imgs, ids, args.max_natural))
    finally:
        model.close()
    args.out.write_text(json.dumps(doc), encoding="utf-8")
    print(f"behavioural fingerprint of {args.model.name}: {len(doc['probes'])} probes → {args.out}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("verify", help="verify a signed ledger (standalone verifier)")
    p.add_argument("ledger", nargs="?", type=Path)
    p.add_argument("--ledger", dest="ledger_opt", type=Path, help="ledger JSONL (alternative to the positional form)")
    p.add_argument("--trust-root", type=Path, required=True)
    p.add_argument("--anchor", type=Path, help="external Merkle anchor file")
    p.add_argument("--inputs", type=Path, help="directory with the raw inputs referenced by records")
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=_cmd_verify)

    p = sub.add_parser("keys", help="generate an Ed25519 signing key")
    p.add_argument("action", choices=["generate"])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--roles", default="ledger,anchor", help="comma-separated roles: ledger, audit, anchor, report")
    p.add_argument("--comment", default="")
    p.add_argument("--force", action="store_true")
    p.set_defaults(handler=_cmd_keys)

    p = sub.add_parser("trust-root", help="create a trust root from keys and approved models")
    p.add_argument("action", choices=["init"])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--name", default="VisionSentinel trust root")
    p.add_argument("--key", action="append", required=True, help="KEY.pem[:roles] (repeatable)")
    p.add_argument("--approve-model", action="append", help="model artifact to approve (repeatable)")
    p.add_argument("--approver", default="operator")
    p.set_defaults(handler=_cmd_trust_root)

    p = sub.add_parser("infer", help="run protected inference and append signed records to a ledger")
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--preprocess", type=Path)
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--key", type=Path, required=True)
    p.add_argument("--anchor", type=Path, help="append external Merkle anchors to this file")
    p.add_argument("--checkpoint-every", type=int, default=64)
    p.set_defaults(handler=_cmd_infer)

    p = sub.add_parser("drift", help="compare incoming operational data with a reference")
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--incoming", type=Path, required=True)
    p.add_argument("--model", type=Path, help="optional model for predicted-class shift")
    p.add_argument("--profile", default="baseline")
    p.add_argument("--out", type=Path, default=Path("reports"))
    p.set_defaults(handler=_cmd_drift)

    p = sub.add_parser("model", help="model utilities")
    p.add_argument("action", choices=["fingerprint"])
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--preprocess", type=Path)
    p.add_argument("--probe", type=Path, help="clean probe corpus for natural probes")
    p.add_argument("--max-natural", type=int, default=64)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(handler=_cmd_fingerprint)
