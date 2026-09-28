"""CLI sub-commands."""

from __future__ import annotations

import argparse
import json

from ..contracts import ATTACK_CLASSES
from ..core.profiles import list_profiles, load_profile
from ..engine.registry import default_registry
from .output import heading, table


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


def register_all(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("profiles", help="list, show or validate assessment profiles")
    p.add_argument("action", choices=["list", "show", "validate"])
    p.add_argument("name", nargs="?", default="baseline")
    p.set_defaults(handler=_cmd_profiles)

    p = sub.add_parser("detectors", help="list registered detectors and their declarations")
    p.add_argument("id", nargs="?", help="show the full declaration of one detector")
    p.set_defaults(handler=_cmd_detectors)
