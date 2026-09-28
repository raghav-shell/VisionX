"""Trigger artifacts, contributor risk and the evidence graph on the shared clean/attacked corpora."""

from __future__ import annotations

import numpy as np
import pytest

from tests.scientific.conftest import SEED, _records
from visionsentinel.attacklab import data_attacks as atk
from visionsentinel.attacklab.corpus import load_truth, write_corpus
from visionsentinel.core.workspace import Workspace
from visionsentinel.engine.request import ScanRequest
from visionsentinel.engine.scan import run_scan


def _poisoned(truth, *attacks):
    return {k for k, v in truth.items() if set(v["attacks"]) & set(attacks)}


def test_clean_corpus_has_no_trigger_findings(clean_scan):
    result, _ = clean_scan
    assert not [f for f in result.findings if f.detector_id == "data.trigger_artifact"]


def test_patch_trigger_is_found_exactly_and_graded(attacked_scan):
    result, _, truth = attacked_scan
    trig = [f for f in result.findings if f.attack_class == "localized_trigger" and f.detector_id == "data.trigger_artifact"]
    assert len(trig) == 1
    f = trig[0]
    members = {s.sample_id for s in f.affected_samples}
    assert members <= _poisoned(truth, "localized_trigger")
    assert len(members) >= 8
    assert f.affected_contributors == ["Delta"]
    assert f.tags["target_class"] == "civilian_vehicle" and f.tags["region"] == "bottom-right"
    assert {"pattern repetition", "contributor concentration", "class correlation"} <= set(f.corroborating_signals)
    assert "backdoor" not in f.title.lower(), "artifact analysis must not claim a backdoor was found"
    assert f.recommended_disposition.value == "REVIEW", "uncalibrated statistical finding must not auto-quarantine"


@pytest.fixture(scope="module")
def blended_scan(corpora):
    recs = _records()
    atk.blended_poison(recs, "Delta", 15, "civilian_vehicle", np.random.default_rng(SEED), alpha=0.12)
    root = corpora["root"] / "blended"
    write_corpus(recs, root, name="blended")
    ws = Workspace(corpora["root"] / "ws-blended").ensure()
    return run_scan(ScanRequest(dataset=root, profile="selftest"), workspace=ws), load_truth(root)


def test_blended_trigger_group_is_found(blended_scan):
    result, truth = blended_scan
    trig = [f for f in result.findings if f.attack_class == "blended_trigger"]
    assert trig
    members = {s.sample_id for f in trig for s in f.affected_samples}
    poisoned = _poisoned(truth, "blended_trigger")
    assert len(members & poisoned) >= 0.8 * len(poisoned)
    assert len(members - poisoned) <= 2


def test_attackers_rank_highest_and_clean_contributor_is_low(attacked_scan):
    result, _, _ = attacked_scan
    ranked = [c.contributor for c in result.contributors]
    tiers = {c.contributor: c.risk_tier for c in result.contributors}
    assert ranked[0] == "Delta" and tiers["Delta"] in ("HIGH", "CRITICAL")
    assert tiers["Charlie"] in ("ELEVATED", "HIGH", "CRITICAL")
    assert tiers["Alpha"] == "LOW"
    delta = result.contributors[0]
    assert delta.flagged > delta.expected_high
    assert delta.campaign_findings and delta.dominant_signals


def test_clean_contributors_all_low(clean_scan):
    result, _ = clean_scan
    assert result.contributors and all(c.risk_tier == "LOW" for c in result.contributors)


def test_evidence_graph_links_contributor_sample_finding_evidence(attacked_scan):
    result, _, _ = attacked_scan
    nodes = {n.id: n for n in result.graph.nodes}
    edges = {(e.source, e.target, e.type) for e in result.graph.edges}
    trig = next(f for f in result.findings if f.attack_class == "localized_trigger" and f.detector_id == "data.trigger_artifact")
    fid = f"finding:{trig.id}"
    sample = f"sample:{trig.affected_samples[0].sample_id}"
    assert (fid, sample, "ABOUT") in edges
    assert (sample, "contributor:Delta", "SUPPLIED_BY") in edges
    assert (sample, "detector:data.trigger_artifact", "FLAGGED_BY") in edges
    assert any(s == fid and t == "class:civilian_vehicle" and k == "CORRELATES_WITH" for s, t, k in edges)
    assert any(s == fid and k == "SUPPORTED_BY" and nodes[t].type == "Evidence" for s, t, k in edges)
