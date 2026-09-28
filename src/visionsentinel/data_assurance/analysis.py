"""Shared, lazily computed analysis of one dataset.

Several detectors need the same expensive intermediates (decoded tensors, perceptual hashes,
embeddings, near-duplicate components, a cross-validated label model). They are computed once per
scan here. Embeddings are cached on disk under a key derived from the dataset digest, the encoder
digest and the preprocessing digest, and loaded with ``allow_pickle=False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Callable

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from ..core.hashing import digest_json, sha256_hex
from ..loaders.datasets import Dataset, Sample
from ..vision.encoders import Encoder, normalise_embeddings
from ..vision.hashing import hash_batch, near_pairs


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = np.arange(n)

    def find(self, i: int) -> int:
        root = i
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[i] != root:
            self.parent[i], i = root, self.parent[i]
        return int(root)

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def components(self) -> np.ndarray:
        return np.array([self.find(i) for i in range(len(self.parent))])


@dataclass
class LabelModel:
    """Out-of-fold class probabilities and neighbourhood agreement for labelled samples."""

    index: np.ndarray            # positions (into analysis arrays) of samples in the model
    proba: np.ndarray            # n × K out-of-fold probabilities
    declared: np.ndarray         # n declared class index
    predicted: np.ndarray        # n argmax class index
    agreement: np.ndarray        # n similarity-weighted share of neighbours with the declared label
    neighbour_class: np.ndarray  # n majority class among neighbours
    neighbours: np.ndarray       # n × k positions (into analysis arrays)
    per_class_threshold: np.ndarray  # K confident-learning thresholds t_j
    oof_accuracy: float
    classes_modelled: list[int]
    scheme: str = "stratified k-fold"

    def p_declared(self) -> np.ndarray:
        return self.proba[np.arange(len(self.declared)), self.declared]

    def p_predicted(self) -> np.ndarray:
        return self.proba[np.arange(len(self.predicted)), self.predicted]


class DatasetAnalysis:
    def __init__(self, dataset: Dataset, *, resolution: int, encoder: Encoder, seed: int,
                 reference: "DatasetAnalysis | None" = None, cache_dir: Path | None = None,
                 emit: Callable[[str], None] | None = None) -> None:
        self.dataset = dataset
        self.resolution = resolution
        self.encoder = encoder
        self.seed = seed
        self.reference = reference
        self.cache_dir = cache_dir
        self.emit = emit or (lambda _m: None)
        self.samples: list[Sample] = dataset.readable
        self.class_index = dataset.class_index()
        self._dup_cache: dict[tuple, np.ndarray] = {}
        self._pairs_cache: dict[tuple, list] = {}

    # ------------------------------------------------------------------ basic arrays
    @property
    def n(self) -> int:
        return len(self.samples)

    @cached_property
    def ids(self) -> list[str]:
        return [s.id for s in self.samples]

    @cached_property
    def labels(self) -> np.ndarray:
        return np.array([self.class_index.get(s.label, -1) if s.label else -1 for s in self.samples], dtype=int)

    @cached_property
    def contributors(self) -> np.ndarray:
        return np.array([s.contributor or "" for s in self.samples], dtype=object)

    @property
    def preprocess_digest(self) -> str:
        return digest_json({"resize": "square-box", "resolution": self.resolution, "colour": "RGB"})

    @cached_property
    def images(self) -> np.ndarray:
        self.emit(f"decoding {self.n} images at {self.resolution}×{self.resolution}")
        out = np.empty((self.n, self.resolution, self.resolution, 3), dtype=np.uint8)
        for i, s in enumerate(self.samples):
            out[i] = self.dataset.load(s, self.resolution)
        return out

    @cached_property
    def hashes(self) -> dict[str, np.ndarray]:
        self.emit("perceptual hashes (pHash/dHash, mirror-aware) computed")
        return hash_batch(self.images)

    # ------------------------------------------------------------------ embeddings
    def _cache_path(self) -> Path | None:
        if self.cache_dir is None:
            return None
        key = sha256_hex(f"{self.dataset.digest}|{self.encoder.digest}|{self.preprocess_digest}".encode())
        return self.cache_dir / "embeddings" / f"{key}.npy"

    @cached_property
    def raw_embeddings(self) -> np.ndarray:
        path = self._cache_path()
        if path is not None and path.is_file():
            arr = np.load(path, allow_pickle=False)
            if arr.shape[0] == self.n:
                self.emit(f"embeddings loaded from cache ({self.encoder.id})")
                return arr
        arr = self.encoder.encode(self.images)
        self.emit(f"embeddings computed with {self.encoder.id} ({arr.shape[1]} dims)")
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp.npy")
            np.save(tmp, arr, allow_pickle=False)
            tmp.replace(path)
        return arr

    @cached_property
    def zscores(self) -> np.ndarray:
        """Per-dimension z-scores (reference statistics when available), magnitude preserved."""
        base = self.reference.raw_embeddings if self.reference is not None else self.raw_embeddings
        mu, sd = base.mean(axis=0), base.std(axis=0)
        return ((self.raw_embeddings - mu) / np.where(sd > 1e-8, sd, 1.0)).astype(np.float32)

    @cached_property
    def embeddings(self) -> np.ndarray:
        ref = self.reference.raw_embeddings if self.reference is not None else None
        return normalise_embeddings(self.raw_embeddings, ref)

    # ------------------------------------------------------------------ near duplicates
    def duplicate_pairs(self, max_phash: int, max_dhash: int, min_cosine: float) -> list[tuple[int, int, int, int, bool, float]]:
        key = (max_phash, max_dhash, round(min_cosine, 6))
        if key not in self._pairs_cache:
            emb = self.embeddings
            out = []
            for i, j, pd, dd, mirrored in near_pairs(self.hashes, max_phash, max_dhash):
                cos = float(emb[i] @ emb[j])
                if cos >= min_cosine or (pd <= 2 and dd <= 3):
                    out.append((i, j, pd, dd, mirrored, cos))
            self._pairs_cache[key] = out
        return self._pairs_cache[key]

    def duplicate_components(self, max_phash: int = 8, max_dhash: int = 10, min_cosine: float = 0.9) -> np.ndarray:
        key = (max_phash, max_dhash, round(min_cosine, 6))
        if key not in self._dup_cache:
            uf = UnionFind(self.n)
            for i, j, *_ in self.duplicate_pairs(max_phash, max_dhash, min_cosine):
                uf.union(i, j)
            self._dup_cache[key] = uf.components()
        return self._dup_cache[key]

    # ------------------------------------------------------------------ label model
    def label_model(self, *, k: int = 10, folds: int = 5, C: float = 0.3, min_class: int = 10,
                    min_group: int = 20, prune_rounds: int = 1) -> LabelModel | None:
        """Out-of-sample class probabilities and neighbour agreement.

        With contributor metadata (≥ 3 contributors of ≥ ``min_group`` labelled samples) the model is
        *contributor-held-out*: each contributor's samples are scored by a classifier trained only on the
        other contributors, and neighbour agreement only counts other contributors' samples. A contributor
        therefore cannot vouch for its own labels, which is what makes a systematic relabelling campaign
        visible even when it dominates a class. Otherwise stratified k-fold is used.

        Prune-and-refit (Confident Learning): after the first pass, samples that are confidently
        mislabelled (classifier ≥ 0.8 for another class, neighbour agreement ≤ 0.25, declared-class
        probability below its class threshold) are removed from every *training* fold and the models are
        refit, so one contributor's poisoned labels cannot distort the model that judges the others.
        """
        key = ("label_model", k, folds, C, min_class, min_group, prune_rounds)
        cached = getattr(self, "_lm_cache", {}).get(key)
        if cached is not None:
            return cached
        labels = self.labels
        counts = np.bincount(labels[labels >= 0], minlength=len(self.class_index))
        keep_classes = [c for c in range(len(counts)) if counts[c] >= max(min_class, folds)]
        if len(keep_classes) < 2:
            return None
        idx = np.nonzero(np.isin(labels, keep_classes))[0]
        remap = {c: i for i, c in enumerate(keep_classes)}
        y = np.array([remap[c] for c in labels[idx]])
        X = self.embeddings[idx] * np.sqrt(self.embeddings.shape[1])
        groups = np.array([c or "__unattributed__" for c in self.contributors[idx]], dtype=object)
        sizes = {g: int((groups == g).sum()) for g in set(groups) if g != "__unattributed__"}
        held_out = sum(1 for n in sizes.values() if n >= min_group) >= 3
        def fit_all(exclude: np.ndarray) -> np.ndarray:
            proba = np.zeros((len(idx), len(keep_classes)))

            def fit_predict(tr: np.ndarray, te: np.ndarray) -> None:
                tr = tr[~exclude[tr]]
                present = np.unique(y[tr])
                if len(present) < 2:
                    return
                clf = LogisticRegression(C=C, max_iter=3000)
                clf.fit(X[tr], y[tr])
                proba[np.ix_(te, present)] = clf.predict_proba(X[te])

            if held_out:
                for g in sorted(set(groups)):
                    if g == "__unattributed__":
                        continue
                    fit_predict(np.nonzero(groups != g)[0], np.nonzero(groups == g)[0])
                un = np.nonzero(groups == "__unattributed__")[0]
                if len(un):
                    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=self.seed % (2**32))
                    for tr, te in skf.split(X, y):
                        te = np.intersect1d(te, un)
                        if len(te):
                            fit_predict(tr, te)
            else:
                skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=self.seed % (2**32))
                for tr, te in skf.split(X, y):
                    fit_predict(tr, te)
            return proba

        scheme = "contributor-held-out" if held_out else "stratified k-fold"
        pruned = np.zeros(len(idx), dtype=bool)
        proba = fit_all(pruned)
        # cosine kNN, excluding self, the sample's near-duplicate component and (held-out scheme) its contributor
        comp = self.duplicate_components()[idx]
        E = self.embeddings[idx]
        sims = E @ E.T
        np.fill_diagonal(sims, -np.inf)
        sims[comp[:, None] == comp[None, :]] = -np.inf
        if held_out:
            same_group = (groups[:, None] == groups[None, :]) & (groups[:, None] != "__unattributed__")
            sims[same_group] = -np.inf
        kk = min(k, len(idx) - 1)
        nbr = np.argpartition(-sims, kk, axis=1)[:, :kk]
        nbr_sims = np.take_along_axis(sims, nbr, axis=1)
        valid = np.isfinite(nbr_sims)
        w = np.where(valid, np.clip(nbr_sims, 0, None) + 1e-6, 0.0)
        same = (y[nbr] == y[:, None]).astype(float)
        agreement = (same * w).sum(1) / np.maximum(w.sum(1), 1e-12)
        votes = np.zeros((len(idx), len(keep_classes)))
        for c in range(len(keep_classes)):
            votes[:, c] = ((y[nbr] == c) * w).sum(1)
        for _ in range(prune_rounds):
            pred = proba.argmax(1)
            t_cls = np.array([proba[y == c, c].mean() if np.any(y == c) else 1.0 for c in range(len(keep_classes))])
            p_pred = proba[np.arange(len(idx)), pred]
            p_decl = proba[np.arange(len(idx)), y]
            issues = (pred != y) & (p_pred >= 0.8) & (agreement <= 0.25) & (p_decl < t_cls[y])
            if not issues.any() or np.array_equal(issues, pruned):
                break
            pruned = issues
            proba = fit_all(pruned)
            scheme = f"{scheme}, pruned-refit ({int(pruned.sum())} excluded from training)"
        pred = proba.argmax(1)
        thresholds = np.array([proba[y == c, c].mean() if np.any(y == c) else 1.0 for c in range(len(keep_classes))])
        model = LabelModel(index=idx, proba=proba, declared=y, predicted=pred, agreement=agreement,
                           neighbour_class=votes.argmax(1), neighbours=idx[nbr], per_class_threshold=thresholds,
                           oof_accuracy=float((pred == y).mean()), classes_modelled=keep_classes, scheme=scheme)
        self._lm_cache = {**getattr(self, "_lm_cache", {}), key: model}
        self.emit(f"label model ({scheme}): out-of-sample accuracy {model.oof_accuracy:.1%} over {len(idx)} samples")
        return model

    def class_name(self, model: LabelModel, local: int) -> str:
        return self.dataset.classes[model.classes_modelled[local]]
