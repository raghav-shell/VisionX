"""CLI behaviour: exit codes, operator-facing errors and written outputs."""

from __future__ import annotations

import json

import pytest

from visionsentinel.attacklab.corpus import ContributorProfile, generate_contributor, write_corpus
from visionsentinel.cli.main import EXIT_UNSAFE, EXIT_USAGE, main


@pytest.fixture()
def small_dataset(tmp_path):
    recs = []
    for name in ("Alpha", "Bravo", "Charlie"):
        recs += generate_contributor(ContributorProfile(name, 25, "EO-A2", f"unit-{name}", session_size=10), seed=9)
    write_corpus(recs, tmp_path / "ds", name="cli")
    return tmp_path / "ds"


def test_profiles_and_detectors_commands(capsys):
    assert main(["profiles", "list"]) == 0
    assert "baseline" in capsys.readouterr().out
    assert main(["profiles", "validate", "strict"]) == 0
    assert main(["detectors"]) == 0
    out = capsys.readouterr().out
    assert "data.label_consistency" in out and "declared unsupported" in out


def test_unknown_profile_is_a_usage_error_with_hint(capsys, workspace, small_dataset):
    assert main(["scan", "--dataset", str(small_dataset), "--profile", "nosuch", "--quiet"]) == EXIT_USAGE
    err = capsys.readouterr().err
    assert "profile 'nosuch' not found" in err and "hint:" in err


def test_scan_writes_result_and_reports_coverage(capsys, workspace, small_dataset, tmp_path):
    out = tmp_path / "reports"
    assert main(["scan", "--dataset", str(small_dataset), "--profile", "selftest", "--out", str(out), "--quiet"]) == 0
    printed = capsys.readouterr().out
    assert "COVERAGE" in printed and "assessment coverage" in printed
    dirs = list(out.glob("SCN-*"))
    assert len(dirs) == 1
    assert {p.name for p in dirs[0].iterdir()} == {"report.json", "report.html", "coverage.md", "manifest.json"}
    result = json.loads((dirs[0] / "report.json").read_text())["result"]
    assert result["status"] == "SEALED" and result["report_digest"].startswith("sha256:")
    assert {e["detector_id"] for e in result["executions"]} >= {"data.near_duplicate", "data.label_consistency"}


def test_unsafe_dataset_is_rejected_with_distinct_exit_code(capsys, workspace, tmp_path):
    root = tmp_path / "evil"
    root.mkdir()
    (root / "manifest.jsonl").write_text(json.dumps({"file": "../../etc/passwd", "label": "x"}) + "\n")
    assert main(["scan", "--dataset", str(root), "--quiet"]) == EXIT_UNSAFE
    assert "rejected:" in capsys.readouterr().err


def test_scan_without_assets_is_refused(workspace):
    with pytest.raises(SystemExit):
        main(["scan", "--quiet"])
