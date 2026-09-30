# Offline installation and deployment preparation

[Documentation home](README.md) · [Getting started](handbook/01-getting-started.md) · [Operations](handbook/12-operations.md)

Prepare dependencies and assets on a connected build machine, verify the transfer, then rehearse on the offline target. Use the same operating-system family, CPU architecture, Python version, and Node version where native dependencies require them. This is a preparation procedure; a complete portable installer has not been validated by this documentation change.

## Current packaging boundary

The frontend uses a running Next.js server with API rewrites. The checked-in Dockerfile expects a static `frontend/out` directory, which the current configuration does not produce. Treat that recipe as requiring alignment before deployment. Do not present `docker compose build` as a working offline installation shortcut until the packaging gate has been closed.

The two-process [quick start](../README.md#quick-start) is the reference topology. A static-export redesign and a packaged Next.js runtime are different implementation options; choose and test one rather than combining their assumptions.

## Prepare a transfer bundle

Include the exact source revision, a compatible Python wheelhouse, an npm cache populated from the lockfile, Python/Node installers if absent on the target, required browser binaries if running E2E, and any approved local model/encoder assets. Include `profiles/`, `scenarios/`, migrations, and the frontend source/runtime assets; a Python wheel alone is not the complete checkout workflow.

Example dependency preparation, from the checkout on the build host, with an existing transfer directory outside the repository:

```bash
python -m pip wheel --wheel-dir /path/to/bundle/wheels ".[dev,torch]"
npm --prefix frontend ci --cache /path/to/bundle/npm-cache
npm --prefix frontend run build
```

Record the environment and installed package versions. Rehearse cache-only installation on a matching disposable target: lifecycle scripts or platform-specific binaries can require additional preparation. Do not copy a virtual environment across incompatible machines and assume it is portable.

Copy the source checkout into the bundle without `.git`, generated workspaces, private keys, credentials, or unrelated local files. Retain the commit identifier separately. Package code and dependencies before checksum generation:

```bash
python scripts/write_checksums.py /path/to/bundle
```

The generated `SHA256SUMS` covers the bundle's files. Retain that manifest through a trusted channel; integrity hashes do not establish that the build host or package source was trustworthy.

## Install on the offline target

Verify the manifest from the bundle root (`sha256sum -c SHA256SUMS` on Linux or `shasum -a 256 -c SHA256SUMS` on macOS). Create a fresh virtual environment. From the transferred checkout, use prepared dependencies:

```bash
python -m pip install --no-index --find-links /path/to/bundle/wheels "visionsentinel[dev,torch]"
npm --prefix frontend ci --offline --cache /path/to/bundle/npm-cache
npm --prefix frontend run build
```

Ensure the wheelhouse contains only the intended project build/version. If a package or binary is missing, return to preparation and rebuild the bundle; avoid quietly enabling downloads during an offline rehearsal. Use a dataset-only dependency bundle when intentionally omitting the torch scenarios.

Start the API and frontend following the authenticated quick start. The backend must use the transferred checkout's profiles, scenarios, and migrations; keep them alongside the workflow and verify discovery. Provision local users interactively on the target. Do not ship seeded passwords or private production signing keys with the source bundle.

## Acceptance evidence

Retain results for profile/scenario validation, one actual assessment, local report opening, independent governance, report/ledger verification, and the air-gap self-test. Check external requests from the intended runtime and inspect worker isolation on the target OS. The browser's README badges/profile links and Swagger UI are not runtime assurance requirements; the README's screenshots, navigation artwork, and contributor images are stored locally.

Before operational use, rehearse backup and restore, document the signing-key custody model, and close the packaging/resource gaps in the [readiness review](sih-readiness.md).
