"""Attack Lab manifest validation is an explicit CLI contract and CI gate."""

import yaml

from visionsentinel.cli.main import EXIT_USAGE, main


def test_attacklab_validate_accepts_checked_in_manifests(capsys):
    assert main(["attacklab", "validate"]) == 0
    assert "Validated" in capsys.readouterr().out


def test_attacklab_validate_rejects_invalid_manifest_directory(tmp_path, capsys):
    manifest = {
        "scenario_id": "invalid-generator",
        "title": "Invalid generator fixture",
        "attack_class": "test",
        "description": "Fixture for CLI validation failure",
        "attack": {"type": "not-registered"},
    }
    (tmp_path / "invalid.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")

    assert main(["attacklab", "validate", "--scenarios-dir", str(tmp_path)]) == EXIT_USAGE
    error = capsys.readouterr().err
    assert "scenario validation failed" in error
    assert "unsupported attack generator" in error
