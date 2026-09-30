# Frontend screenshot provenance

These are browser screenshots of the VisionX frontend in this repository, captured at **1600 × 1000** in Chromium on **30 September 2026**, using the production frontend (`npm run build`, then `next start`). They are not generated mockups. Reduced motion was enabled; no product text, findings, or metrics were replaced for the captures.

| File | View |
| --- | --- |
| `landing.png` | Landing page hero, Hi-Vis night theme |
| `workspace-overview.png` | Assessment overview, night theme |
| `finding-evidence.png` | Findings with the systematic-mislabel inspector open, showing the flagged images |
| `coverage-matrix.png` | Coverage matrix, night theme |

The workspace images show an authenticated backend session (`analyst01`) on the local API. The assessment is the Targeted Label Flip Attack scenario, run from Attack Lab with the `selftest` profile. It completed with `detector_success`, 10 findings, and a `REVIEW` disposition, using the weight-free `classical-v2` descriptor. Unavailable checks remain visible in the coverage view.

The data is synthetic and comes from [the shipped scenario](../../../scenarios/label_flip.yaml). The images are separate from the checked-in full benchmark run.

To refresh the captures, start the API and the production frontend, run the same scenario from Attack Lab, and capture the named views after notifications disappear. Keep the images and their README captions in sync when the interface changes.
