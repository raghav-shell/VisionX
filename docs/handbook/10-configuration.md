# 10 · Configuration reference

[Handbook home](../README.md) · [Project README](../../README.md)

Separate deployment settings from scientific policy. Environment variables configure the API, workspace, and frontend connection. YAML profiles configure assessment access, budget, detector parameters, calibration declarations, and risk rules.

## Common environment settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `VISIONSENTINEL_HOME` | Repository `var/` | Workspace root for generated state. |
| `VISIONSENTINEL_DATABASE_URL` | SQLite in the workspace | Optional database override; alternative deployments need validation. |
| `VISIONX_API_ORIGIN` | `http://127.0.0.1:8000` | Next.js API rewrite destination. |
| `VISIONSENTINEL_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Accepted API Host headers. |
| `VISIONSENTINEL_ALLOWED_ORIGINS` | Empty | Additional trusted browser origins, comma-separated. |
| `VISIONSENTINEL_INSECURE_COOKIES` | Unset | Set `1` only for local HTTP; otherwise cookies are Secure. |
| `VISIONSENTINEL_DEMO` | False | Enables the header-selected read-only demo path. |
| `VISIONX_ANONYMOUS_READ_ONLY` | False | Allows anonymous viewer reads when using the factory launch. |
| `VISIONSENTINEL_SCAN_WORKERS` | `1` | Per-process worker setting, allowed range 1–4. |
| `VISIONSENTINEL_DEFAULT_PROFILE` | `baseline` | Default assessment profile. |
| `VISIONSENTINEL_DASHBOARD` | Unset | Existing static dashboard directory; not produced by current Next.js config. |

The `visionsentinel server` command overrides `anonymous_read_only` to true. For an authenticated demo, use the documented application-factory launch. Changing `VISIONSENTINEL_HOME` after creating users or keys selects a different workspace; it does not migrate existing state.

## Limits and session settings

| Variable | Default |
| --- | ---: |
| `VISIONSENTINEL_MAX_JSON_BYTES` | 1,048,576 |
| `VISIONSENTINEL_MAX_UPLOAD_BYTES` | 2,147,483,648 |
| `VISIONSENTINEL_MAX_ASSET_STORAGE_BYTES` | 10,737,418,240 |
| `VISIONSENTINEL_SESSION_TTL_MINUTES` | 480 |
| `VISIONSENTINEL_LOGIN_ATTEMPTS_PER_MINUTE` | 6 |
| `VISIONSENTINEL_LOGIN_IP_RATE_MULTIPLIER` | 3 |
| `VISIONSENTINEL_MUTATIONS_PER_MINUTE` | 240 |

Session path, SameSite, and HttpOnly settings are also exposed as `VISIONSENTINEL_SESSION_COOKIE_PATH`, `VISIONSENTINEL_SESSION_COOKIE_SAMESITE`, and `VISIONSENTINEL_SESSION_COOKIE_HTTPONLY`. Keep their defaults unless the deployment design requires a reviewed change. Format-specific resource limits can be stricter than the request-size bound.

## Profile changes

Start from one of the shipped [profiles](../../profiles/). Inheritance uses `extends`; access policy can withhold capabilities, and detector configuration records calibration origins. A budget enables eligible work but does not override scientific prerequisites.

Validate before scanning:

```bash
visionsentinel profiles validate baseline
visionsentinel profiles validate strict
visionsentinel profiles validate blackbox
visionsentinel profiles validate selftest
```

Record the effective profile digest in a review. Do not change thresholds solely to make a demo succeed; preserve the previous benchmark and explain any calibration changes.

Defaults and supported environment fields are authoritative in [API settings](../../src/visionsentinel/api/settings.py), [workspace configuration](../../src/visionsentinel/core/workspace.py), and [frontend rewrites](../../frontend/next.config.mjs). API startup is not a general-purpose `.env` loader; export values in the process environment or your reviewed service configuration.

---

[09 · Previous](09-security-governance.md) · [11 · Next](11-api-reference.md)
