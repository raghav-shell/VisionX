"""Reporting: report bundle (JSON, HTML, coverage Markdown, signed manifest) and scan comparison."""

from .compare import compare_scans
from .report import coverage_markdown, verify_manifest, write_report

__all__ = ["compare_scans", "coverage_markdown", "verify_manifest", "write_report"]
