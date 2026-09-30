# VisionX SIH demo guide

[Documentation home](README.md) · [Presenter script and answers](demo-script.md) · [Readiness review](sih-readiness.md)

## Demo objective

Show an evidence-first assessment from live backend execution through findings, coverage, provenance, governance, and a reproducible Attack Lab result.

## Before starting

- Python 3.12 or newer and Node.js 20 or newer.
- Install the project with `make install`.
- Install frontend dependencies with `npm --prefix frontend ci`. The current frontend runs as a separate Next.js server; follow the [root quick start](../README.md#quick-start).
- Keep the demo workspace inside the project-managed local data directory.

## Start commands

```bash
make install
source .venv/bin/activate
visionsentinel users create analyst01 --role analyst --display-name "Lead Analyst"
visionsentinel users create approver01 --role approver --display-name "Assurance Officer"
VISIONSENTINEL_INSECURE_COOKIES=1 \
VISIONSENTINEL_ALLOWED_ORIGINS=http://127.0.0.1:3001 \
python -m uvicorn visionsentinel.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal, run `npm --prefix frontend run dev -- --hostname 127.0.0.1 -p 3001`. The cookie override is only for local HTTP development.

Open `http://127.0.0.1:3001/workspace`. The workspace reads the live VisionX backend; authentication is required for writes and governance actions.

## Five-to-six minute walkthrough

1. Open the workspace and confirm the backend connection indicator.
2. Select **Sign in to server**, authenticate as the analyst, and open **New assessment**.
3. Select a compatible registered asset and a profile published by the backend.
4. Queue the assessment and watch the live activity stream until the scan reaches a terminal state.
5. Inspect the finding, evidence, coverage, detector execution, provenance, and evidence graph views.
6. Acknowledge a finding, assign an owner, add a governance note, and request a disposition change.
7. Sign in as the independent approver and approve or reject the pending decision.
8. Open **Attack Lab**, choose a scenario from the backend catalogue, run it, and follow the linked scan.
9. Open the sealed report and verify its digest or provenance from the CLI.

The scenario catalogue, asset roles, profiles, statuses, dispositions, and governance reason codes are loaded from the backend contracts; the demo does not depend on copied frontend lists.

## Backup demo path

If no asset is available, use a checked-in scenario through the Attack Lab catalogue. If the browser is unavailable, run `visionsentinel attacklab validate` and `make benchmark`, then open the generated files under `benchmarks/`.

## Reset and shutdown

Stop the server with `Ctrl-C`. Reset only the project-managed local workspace after confirming it contains demo data; never pass an arbitrary user directory to a reset command. Preserve reports needed for review before cleanup.

## What the benchmark supports

- The number and status of executed scenarios in the generated report.
- Scenario-level detection outcomes for valid positive controls.
- Positive/negative control composition.
- Material alerts per clean sample under the declared clean-control protocol.

## What it does not support

- A universal sample-level false-positive rate.
- AUROC without compatible labelled continuous scores from both classes.
- A claim that every attack family is detected.
- A security certification or a guarantee about arbitrary third-party model code.

## Verification and evaluation

Use the [verification guide](handbook/08-verification.md) to check reports and signed ledgers with the appropriate trust material. Benchmark regeneration measures scenario outcomes; it is a separate task.

Run `visionsentinel benchmark` to regenerate `benchmarks/latest.json` and `benchmarks/latest.md`. Run `visionsentinel selftest --airgap` for the local air-gap and cryptographic checks.
