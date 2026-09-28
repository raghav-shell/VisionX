"""Shared scientific fixtures: a clean and an attacked multi-contributor corpus, scanned once per session."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from visionsentinel.attacklab import data_attacks as atk
from visionsentinel.attacklab.corpus import ContributorProfile, generate_clean_set, generate_contributor, load_truth, write_corpus
from visionsentinel.core.workspace import Workspace
from visionsentinel.engine.request import ScanRequest
from visionsentinel.engine.scan import run_scan

SEED = 4242
PROFILES = [
    ContributorProfile("Alpha", 100, "EO-A2", "field-unit-1", {"grassland": 2, "forest": 1}, session_size=25),
    ContributorProfile("Bravo", 100, "EO-B1", "field-unit-2", {"desert": 2, "urban": 1}, session_size=25),
    ContributorProfile("Charlie", 100, "UAV-C3", "uav-squadron-3", {"grassland": 1, "urban": 1, "tarmac": 1},
                       session_size=25),
    ContributorProfile("Delta", 100, "SAT-D4", "sat-downlink-4", {"desert": 1, "tarmac": 1, "forest": 1},
                       session_size=25),
]


def _records():
    recs = []
    for p in PROFILES:
        recs += generate_contributor(p, SEED)
    return recs


@pytest.fixture(scope="session")
def corpora(tmp_path_factory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("sci")
    clean = _records()
    write_corpus(clean, root / "clean", name="clean")
    attacked = _records()
    rng = np.random.default_rng(SEED)
    atk.systematic_mislabel(attacked, "Charlie", {"armoured_vehicle": "civilian_vehicle", "truck": "civilian_vehicle"},
                            0.9, rng)
    atk.patch_poison(attacked, "Delta", 10, "civilian_vehicle", rng)
    atk.duplicate_flood(attacked, "Delta", 3, 10, rng, sensor="UAV-X9")
    atk.sloppy_boxes(attacked, "Bravo", 3, rng)
    atk.ood_insertion(attacked, "Bravo", 6, rng, ("truck", "aircraft"))
    write_corpus(attacked, root / "attacked", name="attacked")
    write_corpus(generate_clean_set(300, SEED, "reference"), root / "reference", name="reference")
    return {"root": root, "clean": root / "clean", "attacked": root / "attacked", "reference": root / "reference"}


@pytest.fixture(scope="session")
def clean_scan(corpora):
    ws = Workspace(corpora["root"] / "ws-clean").ensure()
    return run_scan(ScanRequest(dataset=corpora["clean"], reference_dataset=corpora["reference"], profile="selftest"),
                    workspace=ws), ws


@pytest.fixture(scope="session")
def attacked_scan(corpora):
    ws = Workspace(corpora["root"] / "ws-attacked").ensure()
    result = run_scan(ScanRequest(dataset=corpora["attacked"], reference_dataset=corpora["reference"],
                                  profile="selftest"), workspace=ws)
    return result, ws, load_truth(corpora["attacked"])
