# 01 · Getting started

[Handbook home](../README.md) · [Project README](../../README.md)

Start a local assessment workspace with separate analyst and approver accounts. The supported documentation path uses a Python API and a Next.js frontend on loopback. Build-time dependency installation requires connectivity or a prepared offline bundle.

## Prerequisites

Use Python 3.12 and Node.js 22 for the documented setup. Linux offers the strongest available model-worker isolation. Python packaging declares 3.12+, but native model dependencies and platform controls must be checked on the actual machine. There is no published minimum RAM or latency guarantee; record both during rehearsal.

## Install and provision

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,torch]"
npm --prefix frontend ci
visionsentinel users create analyst01 --role analyst --display-name "Lead Analyst"
visionsentinel users create approver01 --role approver --display-name "Assurance Officer"
```

Passwords are prompted interactively. Use `.[dev]` for a lighter dataset-only environment; several model-based scenarios require PyTorch. On Windows, activate with `.venv\Scripts\Activate.ps1`; the POSIX model sandbox is not a promise of equivalent Windows containment.

## Run both services

API terminal, with the environment active:

```bash
VISIONSENTINEL_INSECURE_COOKIES=1 \
VISIONSENTINEL_ALLOWED_ORIGINS=http://127.0.0.1:3001 \
python -m uvicorn visionsentinel.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Frontend terminal:

```bash
npm --prefix frontend run dev -- --hostname 127.0.0.1 -p 3001
```

Open `http://127.0.0.1:3001/workspace`. The frontend forwards `/api/*` to the API. Select **Sign in to server** and authenticate as the analyst. The HTTP cookie override is for loopback development only. PowerShell users should set environment variables through `$env:NAME` before invoking the API command.

The factory launch uses authenticated access by default. The `visionsentinel server` CLI currently forces anonymous read-only access; do not substitute it when rehearsing the sign-in path.

## First useful result

Open **Attack Lab**, select **Targeted Label Flip Attack**, choose `selftest`, and start the scenario. Wait for the job to finish, follow its scan, and inspect **Findings**, **Coverage**, and **Detectors**. The clean installation initially has no completed scans; an empty assessment list is expected.

For a CLI-only check:

```bash
visionsentinel attacklab validate
visionsentinel attacklab run label_flip_targeted --profile selftest
```

This command evaluates the scenario; it does not promise to create the same indexed browser report as the API route. For standalone report export, use `visionsentinel scan --dataset /path/to/dataset --profile baseline --out ./reports` and open the generated `report.json` locally.

## Before presenting

Confirm both processes are reachable, test both accounts, and keep a completed synthetic scan as a fallback. For production frontend commands, use the [root quick start](../../README.md#quick-start). Container packaging currently needs alignment with the frontend runtime; consult [offline installation](../offline-install.md).

---

[Documentation home](../README.md) · [02 · Next](02-core-concepts.md)
