"""Same seed → same corpus and same attack placement (scenario reproducibility)."""

from __future__ import annotations

import numpy as np

from visionsentinel.attacklab import data_attacks as atk
from visionsentinel.attacklab.corpus import ContributorProfile, generate_contributor
from visionsentinel.attacklab.synthetic import CLASSES, render_chip, sample_spec


def _corpus(seed: int):
    return generate_contributor(ContributorProfile("Delta", 30, "SAT-D4", "unit-d", session_size=10), seed)


def test_same_seed_same_images_and_metadata():
    a, b = _corpus(11), _corpus(11)
    assert [r.id for r in a] == [r.id for r in b]
    assert all(np.array_equal(x.image, y.image) for x, y in zip(a, b))
    assert [(r.label, r.timestamp, r.batch, r.bbox) for r in a] == [(r.label, r.timestamp, r.batch, r.bbox) for r in b]


def test_different_seed_differs():
    a, b = _corpus(11), _corpus(12)
    assert not all(np.array_equal(x.image, y.image) for x, y in zip(a, b))


def test_attack_placement_is_seeded():
    def attacked(seed):
        recs = _corpus(5)
        rng = np.random.default_rng(seed)
        ids = atk.patch_poison(recs, "Delta", 6, "truck", rng)
        ids += atk.duplicate_flood(recs, "Delta", 2, 4, rng)
        return ids, recs
    ids1, r1 = attacked(1)
    ids2, r2 = attacked(1)
    assert ids1 == ids2
    assert all(np.array_equal(x.image, y.image) for x, y in zip(r1, r2))
    assert len([r for r in r1 if "localized_trigger" in r.truth]) == 6
    assert len([r for r in r1 if "duplicate_flood" in r.truth]) == 8


def test_trigger_is_stamped_exactly():
    recs = _corpus(5)
    before = {r.id: r.image.copy() for r in recs}
    ids = atk.patch_poison(recs, "Delta", 3, "truck", np.random.default_rng(0), size=5, position="bottom-right")
    patch = atk.trigger_pattern("checker", 5)
    for r in recs:
        if r.id in ids:
            assert np.array_equal(r.image[57:62, 57:62], patch)
            assert r.label == "truck"
            diff = np.any(r.image != before[r.id], axis=-1)
            assert diff[:57, :].sum() == 0 and diff[:, :57].sum() == 0


def test_every_class_renders_a_visible_object():
    rng = np.random.default_rng(0)
    for cls in CLASSES:
        img, bbox = render_chip(sample_spec(rng, cls))
        assert img.shape == (64, 64, 3)
        assert bbox[2] > 4 and bbox[3] > 4
