"""Profile validation: a typo in a security threshold must never be silently ignored."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.helpers import OkDetector, registry_of
from visionsentinel.core import ProfileError, load_profile
from visionsentinel.core.profiles import list_profiles, profiles_dir


def _write(tmp_path: Path, text: str, name: str = "custom") -> Path:
    path = tmp_path / f"{name}.yaml"
    path.write_text(text)
    return path


def _baseline_text() -> str:
    return (profiles_dir() / "baseline.yaml").read_text()


def test_all_shipped_profiles_validate_against_registry():
    from visionsentinel.engine.registry import default_registry

    names = list_profiles()
    assert {"baseline", "strict", "blackbox", "selftest"} <= set(names)
    for name in names:
        p = load_profile(name, default_registry())
        assert p.digest.startswith("sha256:")


def test_unknown_top_level_key_fails(tmp_path):
    path = _write(tmp_path, _baseline_text() + "\nbudgett: DEEP\n")
    with pytest.raises(ProfileError, match="budgett"):
        load_profile(path)


def test_unknown_nested_key_fails(tmp_path):
    text = _baseline_text().replace("prior_strength: 60", "prior_strenght: 60")
    with pytest.raises(ProfileError, match="prior_strenght"):
        load_profile(_write(tmp_path, text))


def test_duplicate_yaml_key_fails(tmp_path):
    text = _baseline_text().replace("budget: STANDARD", "budget: STANDARD\nbudget: FORENSIC")
    with pytest.raises(ProfileError, match="duplicate key"):
        load_profile(_write(tmp_path, text))


def test_unknown_detector_and_bad_detector_param_fail(tmp_path):
    reg = registry_of(OkDetector)
    data = yaml.safe_load(_baseline_text())
    data["detectors"] = {"test.nope": {"params": {}}}
    with pytest.raises(ProfileError, match="unknown detector"):
        load_profile(_write(tmp_path, yaml.safe_dump(data)), reg)
    data["detectors"] = {"test.ok": {"params": {"threshhold": 0.3}}}
    with pytest.raises(ProfileError, match="threshhold"):
        load_profile(_write(tmp_path, yaml.safe_dump(data)), reg)
    data["detectors"] = {"test.ok": {"params": {"threshold": 7}}}
    with pytest.raises(ProfileError, match="threshold"):
        load_profile(_write(tmp_path, yaml.safe_dump(data)), reg)


def test_digest_changes_when_a_threshold_changes(tmp_path):
    a = load_profile(_write(tmp_path, _baseline_text(), "a"))
    b = load_profile(_write(tmp_path, _baseline_text().replace("excess_factor: 2.0", "excess_factor: 2.5"), "b"))
    assert a.digest != b.digest
    assert load_profile(_write(tmp_path, _baseline_text(), "c")).digest == a.digest


def test_extends_merges_and_cycles_are_rejected(tmp_path):
    child = _write(tmp_path, "extends: baseline\nname: child\nbudget: DEEP\n", "child")
    p = load_profile(child)
    assert p.name == "child" and p.budget.value == "DEEP"
    assert p.risk == load_profile("baseline").risk
    a = _write(tmp_path, f"extends: {tmp_path / 'b.yaml'}\nname: a\n", "a")
    _write(tmp_path, f"extends: {a}\nname: b\n", "b")
    with pytest.raises(ProfileError, match="cycle"):
        load_profile(a)


def test_duplicate_policy_rule_ids_rejected(tmp_path):
    data = yaml.safe_load(_baseline_text())
    data["risk"]["rules"].append(dict(data["risk"]["rules"][0]))
    with pytest.raises(ProfileError, match="duplicate policy rule"):
        load_profile(_write(tmp_path, yaml.safe_dump(data)))
