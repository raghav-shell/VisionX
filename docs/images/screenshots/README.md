# Frontend screenshot provenance

These are browser screenshots of the VisionX frontend in this repository, captured at **1600 × 1000** in Chrome on **30 September 2026**, using the production frontend built with `npm run build -- --webpack`. They are not generated mockups. Reduced motion was enabled; no product text, findings, or metrics were replaced for the captures.

| File | View |
| --- | --- |
| `landing.png` | Landing page with the bundled hero video playing |
| `workspace-overview.png` | Assessment overview, light theme |
| `finding-evidence.png` | Findings and label-consistency inspector, dark theme |
| `coverage-matrix.png` | Coverage matrix, light theme |

The workspace images use an actual assessment produced by `run_scenario(load_scenario("label_flip_targeted"), ..., profile="selftest")`, exported with `write_report`, and opened through the workspace's local report import. The scenario completed with `detector_success`, 9 findings, and a `REVIEW` disposition. Python 3.14 was used for this dataset-only capture run; PyTorch was not installed. Unavailable checks remain visible in the report.

The data is synthetic and comes from [the shipped scenario](../../../scenarios/label_flip.yaml). The images demonstrate local report review, not an authenticated backend session. They are separate from the checked-in full benchmark run. Figures in the landing page's demo strip are illustrative, as labeled in the interface.

To refresh the workspace captures, run the same scenario with a disposable workspace, export its `scan_result` through `visionsentinel.reporting.write_report`, open the resulting `report.json` from `/workspace`, and capture the named views after notifications disappear. Use the production frontend build to avoid development overlays. Keep the images and their README captions in sync when the interface changes.
