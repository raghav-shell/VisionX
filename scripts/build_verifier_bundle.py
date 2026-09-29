#!/usr/bin/env python3
"""Create a small, independently runnable, checksummed ledger-verifier bundle."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tarfile
import tempfile
from pathlib import Path


FILES = ("__init__.py", "canonical.py", "merkle.py", "trust.py", "verifier.py")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("dist/visionsentinel-verifier.tar.gz"))
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    source = repo / "src" / "visionsentinel" / "provenance"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "visionsentinel-verifier"
        package = root / "visionsentinel" / "provenance"
        package.mkdir(parents=True)
        (root / "visionsentinel" / "__init__.py").write_text("\n")
        for name in FILES:
            shutil.copy2(source / name, package / name)
        (root / "requirements.txt").write_text("cryptography>=42,<47\n")
        (root / "README.txt").write_text(
            "VisionSentinel independent ledger verifier\n\n"
            "Install only from your approved offline wheelhouse:\n"
            "  python -m pip install --no-index --find-links WHEELS -r requirements.txt\n"
            "Run:\n"
            "  PYTHONPATH=. python -m visionsentinel.provenance.verifier LEDGER --trust-root TRUST.json --anchor ANCHORS.jsonl --json\n"
        )
        manifest = []
        for item in sorted(p for p in root.rglob("*") if p.is_file()):
            manifest.append(f"{digest(item)}  {item.relative_to(root)}")
        (root / "SHA256SUMS").write_text("\n".join(manifest) + "\n")
        with tarfile.open(args.out, "w:gz") as archive:
            archive.add(root, arcname=root.name)
    print(f"wrote {args.out} ({digest(args.out)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
