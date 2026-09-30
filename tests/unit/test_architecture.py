"""Static architecture rules: import layering, no shell execution, no network clients, no unsafe loads."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[2] / "src" / "visionsentinel"

BASE = {"contracts", "core", ""}
ALLOWED: dict[str, set[str]] = {
    "": set(),
    "contracts": {""},
    "core": {"contracts", ""},
    "evidence": BASE,
    "vision": BASE,
    "provenance": BASE,
    "storage": BASE,
    "risk": BASE,
    "loaders": BASE | {"vision"},
    "data_assurance": BASE | {"evidence", "vision", "loaders"},
    "model_assurance": BASE | {"evidence", "vision", "loaders"},
    "drift": BASE | {"evidence", "vision", "loaders"},
    "reporting": BASE | {"evidence", "risk", "provenance"},
    "governance": BASE | {"provenance", "storage"},
    "engine": BASE | {"evidence", "vision", "loaders", "data_assurance", "model_assurance", "drift",
                      "provenance", "risk", "reporting"},
    "attacklab": BASE | {"evidence", "vision", "loaders", "data_assurance", "model_assurance", "drift",
                         "provenance", "risk", "reporting", "engine"},
    "evaluation": BASE | {"evidence", "vision", "loaders", "data_assurance", "model_assurance", "drift",
                          "provenance", "risk", "reporting", "engine", "attacklab"},
    "api": BASE | {"evidence", "vision", "loaders", "data_assurance", "model_assurance", "drift", "provenance",
                   "risk", "reporting", "engine", "attacklab", "evaluation", "governance", "storage"},
    "cli": BASE | {"evidence", "vision", "loaders", "data_assurance", "model_assurance", "drift", "provenance",
                   "risk", "reporting", "engine", "attacklab", "evaluation", "governance", "storage", "api"},
}

# The standalone verifier must run with the standard library and `cryptography` only.
VERIFIER_FILES = {"canonical.py", "merkle.py", "verifier.py", "trust.py", "__init__.py"}


def _modules() -> list[Path]:
    return sorted(p for p in PKG.rglob("*.py"))


def _top(path: Path) -> str:
    rel = path.relative_to(PKG).parts
    return rel[0] if len(rel) > 1 else ""


def _imports(path: Path) -> list[tuple[str, int, ast.AST]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out = []
    pkg_parts = list(path.relative_to(PKG).parts[:-1])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, 0, node))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg_parts[: len(pkg_parts) - (node.level - 1)] if node.level > 1 else pkg_parts
                target = ".".join(["visionsentinel", *base, *([node.module] if node.module else [])])
                out.append((target, node.level, node))
            else:
                out.append((node.module or "", 0, node))
    return out


def _is_type_checking_only(path: Path) -> set[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            for sub in ast.walk(node):
                if hasattr(sub, "lineno"):
                    lines.add(sub.lineno)
    return lines


@pytest.mark.parametrize("path", _modules(), ids=lambda p: str(p.relative_to(PKG)))
def test_import_layering(path: Path):
    layer = _top(path)
    allowed = ALLOWED.get(layer)
    assert allowed is not None, f"package {layer!r} has no layering rule"
    type_only = _is_type_checking_only(path)
    for name, _, node in _imports(path):
        if not name.startswith("visionsentinel") or node.lineno in type_only:
            continue
        parts = name.split(".")
        target = parts[1] if len(parts) > 1 else ""
        if target == layer:
            continue
        assert target in allowed, f"{path.relative_to(PKG)}:{node.lineno} imports {name} (layer {layer!r} may import {sorted(allowed)})"


def test_verifier_has_minimal_dependencies():
    stdlib = set(sys.stdlib_module_names)
    for fname in VERIFIER_FILES:
        path = PKG / "provenance" / fname
        if not path.exists():
            pytest.skip("verifier not present yet")
        type_only = _is_type_checking_only(path)
        module_level = {n.lineno for n in ast.parse(path.read_text(encoding="utf-8")).body}
        for name, level, node in _imports(path):
            root = name.split(".")[0]
            # only imports executed when the module is imported matter; function-local imports run on demand
            if node.lineno in type_only or node.lineno not in module_level:
                continue
            if name.startswith("visionsentinel.provenance"):
                assert name.split(".")[-1] in {f[:-3] for f in VERIFIER_FILES}, f"{fname} imports {name}"
                continue
            assert root in stdlib or root == "cryptography", f"{fname}:{node.lineno} imports {name}"


FORBIDDEN_CALLS = {
    ("os", "system"), ("os", "popen"), ("subprocess", "getoutput"), ("subprocess", "getstatusoutput"),
    ("pickle", "load"), ("pickle", "loads"), ("marshal", "loads"),
}
NETWORK_MODULES = {"requests", "httpx", "aiohttp", "urllib3", "http.client", "urllib.request", "ftplib", "smtplib"}


@pytest.mark.parametrize("path", _modules(), ids=lambda p: str(p.relative_to(PKG)))
def test_no_shell_execution_network_clients_or_unsafe_deserialisation(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "shell":
                    assert not (isinstance(kw.value, ast.Constant) and kw.value.value is True), \
                        f"{path.name}:{node.lineno} uses shell=True"
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                assert (func.value.id, func.attr) not in FORBIDDEN_CALLS, f"{path.name}:{node.lineno} calls {func.value.id}.{func.attr}"
                if func.value.id == "torch" and func.attr == "load":
                    kws = {k.arg: k.value for k in node.keywords}
                    wo = kws.get("weights_only")
                    assert isinstance(wo, ast.Constant) and wo.value is True, f"{path.name}:{node.lineno} torch.load without weights_only=True"
                if func.value.id == "np" and func.attr == "load":
                    kws = {k.arg: k.value for k in node.keywords}
                    ap = kws.get("allow_pickle")
                    assert isinstance(ap, ast.Constant) and ap.value is False, f"{path.name}:{node.lineno} np.load without allow_pickle=False"
                if func.value.id == "yaml" and func.attr in {"load", "unsafe_load", "full_load"}:
                    kws = {k.arg for k in node.keywords}
                    assert "Loader" in kws, f"{path.name}:{node.lineno} yaml.{func.attr} without an explicit safe Loader"
    for name, _, node in _imports(path):
        assert name not in NETWORK_MODULES and name.split(".")[0] not in {"requests", "httpx", "aiohttp", "urllib3"}, \
            f"{path.name}:{node.lineno} imports network client {name}"
