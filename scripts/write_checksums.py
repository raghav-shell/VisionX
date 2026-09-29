#!/usr/bin/env python3
"""Write a SHA-256 manifest for a distributable offline bundle."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    root = args.directory.resolve()
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    output = args.out or root / "SHA256SUMS"
    output.write_text("".join(f"{digest(path)}  {path.relative_to(root)}\n" for path in files), encoding="utf-8")
    print(f"wrote {output} for {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
