# 05 · Data, models, and asset intake

[Handbook home](../README.md) · [Project README](../../README.md)

An assessment is only meaningful when the supplied assets and their roles are explicit. Keep candidate inputs separate from trusted references and record who approved those references.

## Supported input families

| Input | Supported handling | Preparation |
| --- | --- | --- |
| Image datasets | VisionSentinel manifest, COCO, YOLO, Pascal VOC, ImageFolder, plain images | Retain annotations, label mapping, and sample metadata. |
| Candidate models | Supported ONNX and PyTorch-related paths, subject to safe-loader checks | Supply preprocessing and a known architecture where required. |
| Approved model/reference | Artifact, digest, fingerprint, or reference data as appropriate | Establish approval outside the candidate submission. |
| Inference ledger | Signed JSONL records | Supply public trust material and an independently retained anchor when available. |
| Operational batch | Incoming images compared with reference data | Describe collection conditions and expected benign changes. |

Format support does not imply that every detector can run. Native runtime availability, architecture support, safe-loading restrictions, and access policy can all reduce coverage. Arbitrary Python model code is not an accepted extension mechanism.

## Browser and CLI boundaries

The API accepts registered asset IDs in scan fields such as `dataset`, `model`, and `reference_dataset`. Upload/import creates the registry entry. Supplying `/home/operator/model.onnx` in a browser request is not equivalent to selecting a registered model.

The CLI is a local operator interface and accepts filesystem paths. Archives should be imported through the asset boundary before dataset scanning. Run `visionsentinel assets --help` for the current import options and supported kinds.

## Reference quality

Record the reference's provenance, intended domain, label mapping, and preprocessing. A candidate matching an approved digest proves byte identity to that approved artifact; it does not prove that the approved model was safe to begin with. Comparing differently preprocessed models can create misleading behavior differences.

Contributor-risk analysis also depends on sample counts and contributor metadata. Small groups or self-referential calibration must remain visible as limitations.

## Lifecycle and storage

Assets have ACTIVE or ARCHIVED lifecycle state. Archive an input when it should no longer be selected for new work; preserve evidence required to explain existing results. Deletion is a separate operation and should follow the review and retention policy.

Default API limits include a 2 GiB upload bound and a 10 GiB registered-asset quota; these are configurable limits, not a recommendation for hardware capacity. Other JSON, archive, image, and model parsing bounds still apply. See [configuration](10-configuration.md).

Source references: [dataset detection](../../src/visionsentinel/loaders/datasets/__init__.py), [model loaders](../../src/visionsentinel/loaders/models/), [asset routes](../../src/visionsentinel/api/routers/assets.py), and [scan input contract](../../src/visionsentinel/engine/request.py).

---

[04 · Previous](04-architecture.md) · [06 · Next](06-detectors-and-profiles.md)
