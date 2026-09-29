# Report format

A report bundle contains `report.json`, `report.html`, `coverage.md`, and `manifest.json`. The manifest lists SHA-256 digests for every payload and is Ed25519 signed when the workspace report key is configured.

`report.json` contains the sealed result and reproduction information: profile digest, software version, git revision when available, seed, platform, and library versions. The dashboard's **verify signed report** action re-hashes the bundle, verifies the manifest signature against the active report key, and compares an optional expected result digest.

Use report digest comparison only for scans with equivalent assets and profile; a differing digest alone is not a security verdict.
