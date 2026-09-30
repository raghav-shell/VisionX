"""CLI sub-commands."""

from __future__ import annotations

import argparse
import json

from pathlib import Path

from ..contracts import ATTACK_CLASSES, Disposition, Role
from ..core.errors import ConfigurationError
from ..core.profiles import list_profiles, load_profile
from ..core.workspace import Workspace
from ..engine.registry import default_registry
from .output import heading, paint, state, table


def _cmd_profiles(args: argparse.Namespace) -> int:
    registry = default_registry()
    if args.action == "list":
        rows = []
        for name in list_profiles():
            p = load_profile(name, registry)
            rows.append([p.name, p.budget.value, ",".join(c.value for c in p.access.deny) or "—", p.digest[7:19]])
        print(table(rows, ["PROFILE", "BUDGET", "WITHHELD ACCESS", "DIGEST"]))
        return 0
    profile = load_profile(args.name, registry)
    if args.action == "validate":
        print(f"profile {profile.name!r} is valid · digest {profile.digest}")
        return 0
    print(json.dumps(profile.model_dump(mode="json"), indent=2))
    return 0


def _cmd_detectors(args: argparse.Namespace) -> int:
    registry = default_registry()
    if args.id:
        print(json.dumps(registry.get(args.id).spec.model_dump(mode="json"), indent=2))
        return 0
    rows = [[s.id, s.version, s.layer.value, s.min_budget.value, s.calibration.value,
             ",".join(sorted(a.attack_class for a in s.supports))] for s in registry.specs()]
    print(heading(f"{len(rows)} registered detectors"))
    print(table(rows, ["DETECTOR", "VERSION", "LAYER", "MIN BUDGET", "CALIBRATION", "ATTACK CLASSES"]))
    unsupported = [a for a in ATTACK_CLASSES.values() if a.unsupported_reason]
    print()
    print(heading(f"{len(unsupported)} attack classes declared unsupported"))
    for a in unsupported:
        print(f"  {a.id:28s} {a.unsupported_reason}")
    return 0


def print_scan(result) -> None:
    print()
    print(heading("CAPABILITIES"))
    for rec in result.capabilities:
        if rec.present:
            print(f"  {rec.capability.value:24s} {state('WITHHELD' if rec.withheld else 'READY', 10)} {rec.note or ''}")
    print()
    print(heading("DETECTORS"))
    rows = [[e.detector_id, e.planned.value, e.state.value, e.mode or "—", str(e.findings), f"{e.runtime_ms / 1000:.2f}s"]
            for e in result.executions]
    print(table(rows, ["DETECTOR", "PLANNED", "STATE", "MODE", "FINDINGS", "TIME"], colour_col=2))
    print()
    print(heading(f"FINDINGS ({len(result.findings)})"))
    for f in result.findings[:25]:
        print(f"  {state(f.severity.value, 8)} {state(f.recommended_disposition.value, 10)} {f.id}  {f.title}")
    if len(result.findings) > 25:
        print(paint(f"  … {len(result.findings) - 25} more in the report", "grey"))
    print()
    print(heading("COVERAGE"))
    print(table([[r.attack_class, r.state.value] for r in result.coverage.rows], ["ATTACK CLASS", "STATE"], colour_col=1))
    s = result.summary
    print()
    print(f"assessment coverage: {s.coverage_assessed}/{s.coverage_total} attack classes fully assessed, "
          f"{s.coverage_partial} partially")
    print(f"overall disposition: {state(s.overall_disposition.value)}  ·  report digest {result.report_digest}")


def _cmd_scan(args: argparse.Namespace) -> int:
    from ..engine.request import ScanRequest
    from ..engine.scan import run_scan

    request = ScanRequest(
        name=args.name, profile=args.profile, dataset=args.dataset, dataset_format=args.format,
        reference_dataset=args.reference_dataset, probe_dataset=args.probe, suspect_inputs=args.suspect_inputs,
        operational_data=args.incoming, model=args.model, reference_model=args.reference_model,
        architecture=args.architecture, preprocess=args.preprocess, reference_fingerprint=args.reference_fingerprint,
        ledger=args.ledger, trust_root=args.trust_root, anchor=args.anchor, inference_inputs=args.inference_inputs)
    if not request.supplied():
        raise SystemExit("error: supply at least one asset (e.g. --dataset DIR or --model FILE)")

    def on_event(ev) -> None:
        if not args.quiet:
            colour = {"error": "red", "warn": "amber", "stage": "cyan"}.get(ev.level, "grey")
            print(paint(f"{ev.t_ms / 1000:6.2f}s  {ev.message}", colour))

    result = run_scan(request, workspace=Workspace.default(), on_event=on_event)
    print_scan(result)
    out: Path = args.out
    written = write_outputs(result, out, args.sign_with)
    print()
    for p in written:
        print(f"wrote {p}")
    return 1 if result.summary.overall_disposition == Disposition.QUARANTINE and args.fail_on_quarantine else 0


def write_outputs(result, out: Path, signing_key: Path | None = None) -> list[Path]:
    from ..evidence.store import EvidenceStore
    from ..provenance.keys import load_private_key
    from ..reporting import write_report

    key = load_private_key(signing_key) if signing_key else None
    paths = write_report(result, out, EvidenceStore(Workspace.default().evidence), key)
    return list(paths.values())


def _scan_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("assets")
    g.add_argument("--dataset", type=Path, help="training dataset directory (manifest/COCO/YOLO/VOC/ImageFolder/images)")
    g.add_argument("--format", default="auto", help="dataset format (default: auto-detect)")
    g.add_argument("--reference-dataset", type=Path, help="trusted clean reference dataset")
    g.add_argument("--probe", type=Path, help="clean labelled probe corpus for model testing")
    g.add_argument("--suspect-inputs", type=Path, help="operational inputs suspected of carrying a trigger (STRIP)")
    g.add_argument("--incoming", type=Path, help="incoming operational images for drift analysis")
    g.add_argument("--model", type=Path, help="candidate model (.onnx, TorchScript .pt, state dict, .safetensors)")
    g.add_argument("--reference-model", type=Path, help="approved reference model")
    g.add_argument("--architecture", help="known architecture id for bare state dicts")
    g.add_argument("--preprocess", type=Path, help="preprocessing configuration JSON")
    g.add_argument("--reference-fingerprint", type=Path, help="stored behavioural fingerprint of the approved model")
    g.add_argument("--ledger", type=Path, help="signed inference ledger (JSONL)")
    g.add_argument("--trust-root", type=Path, help="trust root JSON (keys and approved bindings)")
    g.add_argument("--anchor", type=Path, help="external Merkle anchor file")
    g.add_argument("--inference-inputs", type=Path, help="directory of raw inputs referenced by the ledger")
    p.add_argument("--profile", default="baseline", help="assessment profile (default: baseline)")
    p.add_argument("--name", default="assessment", help="human-readable scan name")
    p.add_argument("--out", type=Path, default=Path("reports"), help="output directory for reports")
    p.add_argument("--quiet", action="store_true", help="suppress the live event stream")
    p.add_argument("--fail-on-quarantine", action="store_true", help="exit 1 when the overall disposition is QUARANTINE")
    p.add_argument("--sign-with", type=Path, help="Ed25519 key (role 'report') to sign the report manifest")


def _load_result(path: Path):
    from ..contracts import ScanResult

    doc = json.loads(Path(path).read_text())
    return ScanResult.model_validate(doc.get("result", doc))


def _cmd_compare(args: argparse.Namespace) -> int:
    from ..reporting import compare_scans

    diff = compare_scans(_load_result(args.a), _load_result(args.b))
    if args.json:
        print(json.dumps(diff, indent=1))
        return 0
    s = diff["summary"]
    print(heading(f"COMPARE {diff['a']['scan_id']} → {diff['b']['scan_id']}"))
    rows = [["assessment coverage", f"{s['coverage_pct'][0]}%", f"{s['coverage_pct'][1]}%"],
            ["critical findings", str(s["critical"][0]), str(s["critical"][1])],
            ["quarantine", str(s["quarantine"][0]), str(s["quarantine"][1])],
            ["review", str(s["review"][0]), str(s["review"][1])],
            ["overall disposition", str(s["overall"][0]), str(s["overall"][1])]]
    rows += [[f"{c['role'].lower()} digest", "", c["status"]] for c in diff["asset_changes"]]
    print(table(rows, ["", "A", "B"]))
    print()
    for line in diff["explanation"]:
        print(f"  • {line}")
    return 0


def _cmd_schemas(args: argparse.Namespace) -> int:
    from ..reporting.schemas import export_schemas

    for p in export_schemas(args.out):
        print(f"wrote {p}")
    return 0


def _cmd_server(args: argparse.Namespace) -> int:
    import uvicorn
    from ..api.app import create_app
    from ..api.settings import Settings

    settings = Settings.from_env(
        demo_mode=args.demo,
        dashboard_dir=args.dashboard,
    )
    app = create_app(settings=settings)
    print(heading(f"Starting VisionSentinel server on {args.host}:{args.port}"))
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def _cmd_selftest(args: argparse.Namespace) -> int:
    from ..api.selftest import run_selftest

    res = run_selftest(check_frontend=not args.skip_frontend)
    print(res.summary())
    return 0 if res.passed else 1


def _cmd_users(args: argparse.Namespace) -> int:
    """Provision local dashboard users without ever placing passwords in shell history."""
    from getpass import getpass

    from ..governance import create_user
    from ..storage import Database

    workspace = Workspace.default().ensure()
    db = Database(workspace.database_url)
    if args.action == "create":
        if not args.username:
            raise SystemExit("error: username is required for 'users create'")
        password = getpass("Password: ")
        confirmation = getpass("Confirm password: ")
        if password != confirmation:
            raise SystemExit("error: passwords do not match")
        user = create_user(db, args.username, password, Role(args.role.upper()), args.display_name)
        print(f"Created {user.role.lower()} account {user.username!r} in {workspace.root}")
        return 0

    from sqlalchemy import select
    from ..storage import User

    with db.session() as session:
        rows = session.scalars(select(User).order_by(User.username)).all()
    print(table([[u.username, u.display_name, u.role, "disabled" if u.disabled else "active"] for u in rows],
                ["USERNAME", "DISPLAY NAME", "ROLE", "STATUS"]))
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    from ..evaluation.benchmark import run_benchmark, write_benchmark_artifacts

    report = run_benchmark(workspace=Workspace.default(), profile=args.profile)
    print(heading("VISION SENTINEL — SCIENTIFIC EVALUATION BENCHMARK"))
    print(report.summary_table)
    print()
    mean_tpr = f"{report.mean_tpr:.2f}" if report.mean_tpr is not None else "not estimated"
    mean_fpr = f"{report.mean_fpr:.2f}" if report.mean_fpr is not None else "not estimated (no negative controls)"
    print(f"Total Scenarios: {report.total_scenarios_run} | Passed: {report.passed_scenarios} | Mean TPR: {mean_tpr} | Mean FPR: {mean_fpr}")
    json_path, markdown_path = write_benchmark_artifacts(report)
    print(f"Saved benchmark artifacts to {json_path} and {markdown_path}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report.to_dict(), indent=2, allow_nan=False))
        print(f"Saved benchmark report to {args.out}")
    return 0 if report.passed_scenarios == report.total_scenarios_run else 1


def _cmd_attacklab(args: argparse.Namespace) -> int:
    from ..attacklab.runner import list_scenarios, load_scenario, run_scenario, validate_scenarios

    if args.action == "list":
        scenarios = list_scenarios()
        rows = [[s.scenario_id, s.attack_class, s.evaluation_family, s.title] for s in scenarios]
        print(heading(f"{len(scenarios)} ATTACK LAB SCENARIOS"))
        print(table(rows, ["SCENARIO ID", "ATTACK CLASS", "TIER", "TITLE"]))
        return 0

    if args.action == "validate":
        try:
            scenarios = validate_scenarios(args.scenarios_dir)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        print(f"Validated {len(scenarios)} Attack Lab manifests against the live detector registry")
        return 0

    manifest = load_scenario(args.scenario)
    print(heading(f"RUNNING SCENARIO: {manifest.title} ({manifest.scenario_id})"))
    res = run_scenario(manifest, workspace=Workspace.default(), profile=args.profile)
    status_tag = state("PASS" if res.detected_expected_signals else "FAIL")
    print(f"Detection Status: {status_tag} | Disposition: {state(res.overall_disposition)} | Findings: {res.findings_count}")
    print(f"Report Digest: {res.report_digest}")
    return 0 if res.detected_expected_signals else 1


def _cmd_assets(args: argparse.Namespace) -> int:
    from ..api.assets import import_path
    from ..storage import Asset, Database

    ws = Workspace.default().ensure()
    db = Database(ws.database_url)

    if args.action == "list":
        with db.session() as s:
            assets = s.query(Asset).all()
            rows = [[a.id, a.kind, a.name, a.digest[:16] + "..." if a.digest else "—", a.path] for a in assets]
            print(heading(f"{len(assets)} REGISTERED ASSETS"))
            print(table(rows, ["ID", "KIND", "NAME", "DIGEST", "PATH"]))
        return 0

    if args.action == "import":
        a = import_path(db, ws, Path(args.path), kind=args.kind, name=args.name, copy=not args.no_copy)
        print(f"Imported asset {a.id} ({a.kind}: {a.name})")
        return 0

    return 0


def register_all(sub: argparse._SubParsersAction) -> None:
    from . import provenance_cmds

    p = sub.add_parser("scan", help="run an assurance scan over the supplied assets",
                       description="Probe the supplied assets, negotiate every detector, run the plan and write reports.")
    _scan_args(p)
    p.set_defaults(handler=_cmd_scan)

    p = sub.add_parser("profiles", help="list, show or validate assessment profiles")
    p.add_argument("action", choices=["list", "show", "validate"])
    p.add_argument("name", nargs="?", default="baseline")
    p.set_defaults(handler=_cmd_profiles)

    p = sub.add_parser("detectors", help="list registered detectors and their declarations")
    p.add_argument("id", nargs="?", help="show the full declaration of one detector")
    p.set_defaults(handler=_cmd_detectors)

    provenance_cmds.register(sub)

    p = sub.add_parser("compare", help="compare two scan reports (report.json)")
    p.add_argument("a", type=Path)
    p.add_argument("b", type=Path)
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=_cmd_compare)

    p = sub.add_parser("schemas", help="export JSON Schemas for contracts, profiles, ledgers and trust roots")
    p.add_argument("--out", type=Path, default=Path("schemas"))
    p.set_defaults(handler=_cmd_schemas)

    p = sub.add_parser("server", help="start the VisionSentinel API backend & static dashboard server")
    p.add_argument("--host", default="127.0.0.1", help="host address to bind (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8000, help="port number (default: 8000)")
    p.add_argument("--dashboard", type=Path, default=None, help="custom path to static dashboard build")
    p.add_argument("--demo", action="store_true", help="enable demo mode")
    p.set_defaults(handler=_cmd_server)

    p = sub.add_parser("users", help="provision or list local dashboard accounts")
    p.add_argument("action", choices=["create", "list"])
    p.add_argument("username", nargs="?", help="lowercase username (required for create)")
    p.add_argument("--role", choices=[r.value.lower() for r in Role], default="viewer")
    p.add_argument("--display-name", default=None)
    p.set_defaults(handler=_cmd_users)

    p = sub.add_parser("selftest", help="run offline air-gap self-test and cryptographic verification")
    p.add_argument("--airgap", action="store_true", help="enforce air-gap assertions")
    p.add_argument("--skip-frontend", action="store_true", help="skip scanning frontend static files")
    p.set_defaults(handler=_cmd_selftest)

    p = sub.add_parser("benchmark", help="run the scientific evaluation benchmark suite")
    p.add_argument("--profile", default="selftest", help="profile for benchmark runs (default: selftest)")
    p.add_argument("--out", type=Path, default=None, help="optional path to save benchmark JSON report")
    p.set_defaults(handler=_cmd_benchmark)

    p = sub.add_parser("attacklab", help="manage and run reproducible Attack Lab adversarial scenarios")
    p.add_argument("action", choices=["list", "run", "validate"])
    p.add_argument("scenario", nargs="?", default="label_flip", help="scenario ID or YAML file path")
    p.add_argument("--scenarios-dir", type=Path, default=None,
                   help="directory of manifests to validate (validate action only)")
    p.add_argument("--profile", default="selftest", help="assessment profile")
    p.set_defaults(handler=_cmd_attacklab)

    p = sub.add_parser("assets", help="manage workspace assets")
    p.add_argument("action", choices=["list", "import"])
    p.add_argument("path", nargs="?", type=Path, help="source file or directory to import")
    from ..api.assets import KINDS
    p.add_argument("--kind", default=KINDS[0], choices=KINDS)
    p.add_argument("--name", default=None, help="optional human-readable name")
    p.add_argument("--no-copy", action="store_true", help="reference in-place without copying")
    p.set_defaults(handler=_cmd_assets)
