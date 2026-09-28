"""Protected inference: run a model and append a signed record binding input, model, config and output.

The caller supplies both the raw input bytes (whose digest is bound) and the decoded image (decoded by the
loaders' safe decoder); this module never parses untrusted files itself.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .. import SOFTWARE_ID
from ..core.hashing import digest_json, sha256_digest
from .canonical import canonical_bytes, sha256_hex
from .ledger import LedgerWriter


class InferenceRecorder:
    def __init__(self, model: Any, writer: LedgerWriter, *, inference_config: dict[str, Any] | None = None) -> None:
        self.model = model
        self.writer = writer
        self.inference_config = inference_config or {"top_k": 1, "threshold": "none"}
        self.config_digest = digest_json(self.inference_config)

    def record(self, data: bytes, name: str, image: np.ndarray) -> dict:
        probs = self.model.predict_proba(image[None])[0]
        classes = self.model.class_names or [str(i) for i in range(len(probs))]
        k = int(np.argmax(probs))
        output = {"label": classes[k], "index": k, "scores": [f"{float(p):.6f}" for p in probs],
                  "classes_digest": "sha256:" + sha256_hex(canonical_bytes(classes))}
        body = {"input_digest": sha256_digest(data), "input_ref": name, "model_digest": self.model.artifact_digest,
                "preprocess_digest": self.model.cfg.digest, "inference_config_digest": self.config_digest,
                "software": SOFTWARE_ID, "output": output, "output_digest": "sha256:" + sha256_hex(canonical_bytes(output))}
        return self.writer.append("inference", body)
