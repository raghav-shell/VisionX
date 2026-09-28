"""Terminal output helpers (no third-party dependency, honours NO_COLOR)."""

from __future__ import annotations

import os
import sys

_COLOURS = {
    "red": "31", "green": "32", "amber": "33", "blue": "34", "cyan": "36", "grey": "90", "bold": "1",
}

STATE_COLOUR = {
    "READY": "green", "ASSESSED": "green", "VALID": "green", "COMPLETED": "green", "ACCEPT": "green",
    "PASS": "green", "NONE": "green",
    "DEGRADED": "amber", "PARTIALLY_ASSESSED": "amber", "COMPLETED_DEGRADED": "amber", "REVIEW": "amber",
    "ABSTAINED": "amber", "WARN": "amber", "BUDGET_EXCLUDED": "grey", "NOT_RUN": "grey", "NOT_ASSESSED": "grey",
    "UNAVAILABLE": "grey", "UNSUPPORTED": "grey", "SKIP": "grey",
    "ERROR": "red", "FAILED": "red", "FAILED_TO_EXECUTE": "red", "QUARANTINE": "red", "UNTRUSTED": "red",
    "FAIL": "red", "CRITICAL": "red", "HIGH": "red", "MEDIUM": "amber", "LOW": "cyan", "INFO": "grey",
}


def _enabled(stream) -> bool:
    return stream.isatty() and not os.environ.get("NO_COLOR")


def paint(text: str, colour: str, stream=sys.stdout) -> str:
    if not _enabled(stream) or colour not in _COLOURS:
        return text
    return f"\033[{_COLOURS[colour]}m{text}\033[0m"


def state(text: str, width: int = 0, stream=sys.stdout) -> str:
    return paint(text.ljust(width), STATE_COLOUR.get(text, "bold"), stream)


def heading(text: str) -> str:
    return paint(text, "bold")


def table(rows: list[list[str]], headers: list[str], colour_col: int | None = None) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    out = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)),
           "  ".join("-" * w for w in widths)]
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            cells.append(state(cell, widths[i]) if i == colour_col else cell.ljust(widths[i]))
        out.append("  ".join(cells).rstrip())
    return "\n".join(out)
