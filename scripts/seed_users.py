#!/usr/bin/env python3
"""Idempotently provision local accounts from a permission-restricted JSON file.

The file is never copied into the image or repository. Its schema is:
{"users": [{"username": "analyst01", "password": "...", "role": "ANALYST",
            "display_name": "Lead Analyst"}]}
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from visionsentinel.contracts import Role
from visionsentinel.core.workspace import Workspace
from visionsentinel.governance import create_user
from visionsentinel.storage import Database


def main(path_arg: str) -> int:
    path = Path(path_arg)
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise SystemExit("seed-user file must not be group/world readable (use chmod 0600)")
    document = json.loads(path.read_text(encoding="utf-8"))
    users = document.get("users") if isinstance(document, dict) else None
    if not isinstance(users, list) or not users:
        raise SystemExit("seed-user file must contain a non-empty 'users' list")

    db = Database(Workspace.default().ensure().database_url)
    for item in users:
        if not isinstance(item, dict):
            raise SystemExit("every seeded user must be an object")
        try:
            username = item["username"]
            password = item["password"]
            role = Role(str(item["role"]).upper())
        except (KeyError, ValueError) as exc:
            raise SystemExit("seeded users require username, password and a valid role") from exc
        try:
            create_user(db, str(username), str(password), role, item.get("display_name"))
            print(f"provisioned local {role.value.lower()} account {username!r}")
        except Exception as exc:  # existing users are intentionally preserved across restarts
            if "already exists" not in str(exc):
                raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]) if len(sys.argv) == 2 else "usage: seed_users.py USERS.json")
