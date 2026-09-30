# 13 · Development and contribution guide

[Handbook home](../README.md) · [Project README](../../README.md)

Make changes against explicit contracts and retain evidence of the behavior they affect. Prefer a focused pull request with a reproducible example, appropriate checks, and documented limitations.

## Set up

Follow [getting started](01-getting-started.md) with the `dev` extra. Use `torch` when running model-based scientific fixtures. Read applicable `AGENTS.md` instructions before editing scoped source; the frontend also carries version-specific Next.js guidance.

## Choose the relevant checks

| Change | Checks |
| --- | --- |
| Profiles, detector declarations | `make profiles`, `make detectors`, manifest validation. |
| Backend behavior | Relevant unit/integration tests; broaden for changed contracts. |
| Input boundary or governance | Relevant tests under `tests/security` plus integration coverage. |
| Scientific detectors | Positive and negative controls, `tests/scientific`, benchmark evidence. |
| Frontend UI/contracts | Production build and relevant Playwright workflows. |
| Documentation | Resolve links/anchors, check commands against source, inspect any changed images. |

```bash
python -m pytest tests/unit tests/integration tests/security tests/regression -q
python -m pytest tests/scientific -q
visionsentinel attacklab validate
visionsentinel selftest --airgap
npm --prefix frontend run build
(cd frontend && npx playwright install chromium)
make e2e
```

These are repository verification commands, not an assertion that this documentation edit ran the complete suite. The [quality workflow](../../.github/workflows/quality.yml) separates backend, scientific, frontend, and browser jobs. Record actual outcomes and skips instead of copying a test count from an earlier revision.

## Add a detector

1. Define a stable detector ID and `DetectorSpec` with layer, attack support, capabilities, budget, and calibration metadata.
2. Implement validated parameters, scientific preconditions, and `run(DetectorContext)` with a `DetectorResult`.
3. Produce evidence and documented limitations; use explicit abstention when the evidence cannot support a conclusion.
4. Register through the appropriate assurance package and validate the registry.
5. Exercise missing access, degraded mode, execution errors, and final coverage as well as the positive signal.
6. Add held-out clean and attack controls when making scientific claims. Keep calibration separate from evaluation.

Source contracts: [detector interface](../../src/visionsentinel/core/detector.py) and [registry](../../src/visionsentinel/engine/registry.py).

## Change API contracts

Update the Pydantic body/response definitions, discoverable metadata where relevant, frontend consumers, and integration tests together. Browser requests must continue to use registered asset IDs. Keep job execution success separate from scientific scenario outcomes; preserve failure details and terminal-state semantics.

## Pull request checklist

- Explain the triggering problem and the resulting behavior.
- Link a reproducible scenario or include a minimal example.
- State the exact checks run and any skips or environment restrictions.
- Update relevant handbook pages, exported schemas, and affected screenshots.
- Keep private keys, accounts, raw operational data, and generated workspace state out of Git.

For benchmark changes, retain honest misses and fitness exclusions. A passing build does not establish detector accuracy or deployment readiness.

---

[12 · Previous](12-operations.md) · [14 · Next](14-demo-guide.md)
