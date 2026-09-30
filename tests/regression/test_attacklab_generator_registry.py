"""The Attack Lab manifest, validation, and runtime generator contracts stay aligned."""

from pathlib import Path

from visionsentinel.attacklab.runner import (
    GENERATOR_REGISTRY,
    ScenarioManifest,
    list_scenarios,
    validate_scenarios,
)
from visionsentinel.attacklab.synthetic import CLASSES
from visionsentinel.core.workspace import Workspace
from visionsentinel.core.determinism import rng_for
from visionsentinel.engine.request import ScanRequest


def test_every_registered_generator_has_an_executable_handler():
    assert GENERATOR_REGISTRY
    for attack_type, spec in GENERATOR_REGISTRY.items():
        assert spec.attack_type == attack_type
        assert callable(spec.handler)


def test_every_checked_in_manifest_resolves_to_an_executable_generator():
    scenarios_dir = Path("scenarios")
    manifest_paths = sorted(scenarios_dir.glob("*.yaml"))
    discovered = list_scenarios(scenarios_dir)
    validated = validate_scenarios(scenarios_dir)
    assert len(manifest_paths) == len(discovered) == len(validated)
    for manifest in validated:
        spec = GENERATOR_REGISTRY[manifest.attack["type"]]
        assert callable(spec.handler)


def test_random_label_flip_uses_manifest_configuration_and_is_deterministic(tmp_path):
    manifest = ScenarioManifest.model_validate({
        "scenario_id": "random-label-flip-test",
        "title": "Random label flip test",
        "attack_class": "label_flip",
        "description": "registry test",
        "seed": 1234,
        "base": {
            "reference_size": 12,
            "contributors": [{
                "name": "TestContributor", "samples": 12,
                "sensor": "EO-A2", "source": "test",
            }],
            "classes": list(CLASSES),
        },
        "attack": {
            "type": "label_flip_random", "rate": 0.25,
            "contributor": "TestContributor", "classes": list(CLASSES),
        },
    })
    handler = GENERATOR_REGISTRY[manifest.attack["type"]].handler

    def execute(run_dir: Path):
        run_dir.mkdir(parents=True)
        records, affected, _ = handler(
            manifest, Workspace(tmp_path / "workspace"), run_dir,
            ScanRequest(), rng_for(manifest.seed, "scenario", manifest.scenario_id),
        )
        return [(record.id, record.label, tuple(record.truth)) for record in records], affected

    first, first_affected = execute(tmp_path / "first")
    second, second_affected = execute(tmp_path / "second")
    assert first == second
    assert first_affected == second_affected
    assert len(first_affected) == round(manifest.attack["rate"] * manifest.base["contributors"][0]["samples"])
    assert all("label_flip" in truth for _, _, truth in first if truth)
