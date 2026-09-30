# 11 · API reference

[Handbook home](../README.md) · [Project README](../../README.md)

The API is rooted at `/api`. The current schema is available from the running backend at `http://127.0.0.1:8000/api/openapi.json`; the interactive documentation route is `/api/docs`. Use the JSON schema as the authority for request fields and validation. Interactive Swagger assets may require external availability, so do not rely on that UI during an offline presentation.

## Authentication and request rules

`POST /api/auth/login` accepts `username` and `password`, sets the `vs_session` cookie, and returns the user's identity plus a `csrf` token. `GET /api/auth/me` returns the active session. Authenticated mutations send the cookie and `X-CSRF-Token`; browser origins must be trusted. Login itself is origin-checked.

No API key or bearer-token authentication is documented here. Explicit anonymous/demo configuration grants viewer reads only; it does not authorize uploads, scan creation, or governance mutations.

## Endpoint map

| Area | Representative operations | Contract |
| --- | --- | --- |
| Discovery | `GET /api/system/info`, `/metadata`, `/profiles`, `/detectors`, `/sandbox` | Discover product details, enums, profiles, and runtime capability information. |
| Assets | `GET /api/assets`; `POST /api/assets/upload`; `POST /api/assets/{asset_id}/archive` and `/restore` | Upload uses multipart `kind`, `name`, and `file`; retain returned asset IDs. |
| Scans | `POST /api/scans`; `GET /api/scans/{scan_id}` | Submission uses registered asset IDs and a profile. |
| Live activity | `GET /api/scans/{scan_id}/events` | Server-sent events with event IDs and resume support. |
| Assessment views | `GET /api/scans/{scan_id}/plan`, `/findings`, `/coverage`, `/contributors`, `/drift`, `/provenance`, `/graph` | Read the planned and completed evidence. |
| Reports | `GET /api/scans/{scan_id}/report.json`, `/report.html`, `/bundle/{artifact}` | Bundle artifacts are allowlisted. |
| Report check | `POST /api/scans/{scan_id}/report/verify` | Read-only verification operation; optional `expected_digest`. |
| Comparison | `POST /api/scans/compare` | Body names `scan_a` and `scan_b`. |
| Findings | `GET /api/findings/{finding_id}`; `POST` suffixes `/acknowledge`, `/owner`, `/comment`, `/decision` | Analysts manage findings and request disposition changes. |
| Governance | `GET /api/governance/decisions`, `/audit`; `POST /api/governance/decisions/{decision_id}/approve` or `/reject` | Independent approver resolves a pending decision. |
| Attack Lab | `GET /api/attacklab/scenarios`; `POST /api/attacklab/scenarios/{scenario_id}/run` | Returns `202` with a background `job_id`. |
| Jobs | `GET /api/jobs`, `/api/jobs/{job_id}` | Poll terminal status, errors, and result. |
| Drift | `POST /api/drift/analyze` | `incoming_data`, optional reference/model asset IDs, and profile. |
| Provenance | `POST /api/provenance/verify`; `GET /api/provenance/inspect`, `/trust-root`, `/anchors/export` | Verification accepts registered ledger/trust/anchor/input asset IDs. |
| Evidence | `GET /api/evidence/{digest}`, `/raw` | Inspect metadata or retrieve integrity-checked content. |
| Administration | `/api/admin/users` and account operations; provenance trust-root import/revoke/rotate | Administrative mutations require ADMIN and CSRF. |

Scan asset field names such as `dataset` and `model` contain **asset IDs**, not filesystem paths. Do not infer a route's authorization solely from its HTTP verb: verification uses POST but viewer permissions, while state changes require stronger roles.

## Minimal authenticated client

Run this against a disposable demo workspace with a provisioned analyst. It submits one controlled scenario; the password is prompted rather than stored in source.

```python
from getpass import getpass
import httpx

with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
    login = client.post("/api/auth/login", json={
        "username": "analyst01", "password": getpass("Password: ")
    })
    login.raise_for_status()
    headers = {"X-CSRF-Token": login.json()["csrf"]}
    queued = client.post(
        "/api/attacklab/scenarios/label_flip_targeted/run",
        json={"profile": "selftest"}, headers=headers,
    )
    queued.raise_for_status()
    job_id = queued.json()["job_id"]
    print("Queued job:", job_id)
    result = client.get(f"/api/jobs/{job_id}")
    result.raise_for_status()
    print(result.json())
```

One status read does not wait for completion. Poll the job until `terminal` is true, check `status` and `error`, then use `result.scan_id` only when present. A completed job may still contain a scientific detector miss or a fitness failure.

## Events and failure handling

Use `/api/system/metadata` for scan-event names and lifecycle values. Event IDs support `Last-Event-ID` reconnection. The final scan/job record is authoritative; a dropped event stream is not evidence that execution succeeded or failed.

Handle `401` as missing authentication, `403` as authorization/origin/CSRF refusal, `404` as unavailable objects, `409` as state/integrity conflict, `422` as invalid input, `429` as rate limiting, and `503` as unavailable execution or blocked offline-workload activity. Error payload shape varies by handler; preserve `detail`, `error`, and `hint` when available.

For the complete implementation and exact role requirements, see [API routers](../../src/visionsentinel/api/routers/) and [dependencies](../../src/visionsentinel/api/deps.py).

---

[10 · Previous](10-configuration.md) · [12 · Next](12-operations.md)
