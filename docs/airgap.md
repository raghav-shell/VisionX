# Air-gap operations

Install Python wheels and the frontend dependency cache from approved removable media. Build the container on a connected build machine, export it with `docker save`, checksum it, then load it on the target with `docker load`. Detailed commands are in `offline-install.md`.

On the target, run `visionsentinel selftest --airgap` before accepting assets. The service binds to loopback by default. Treat an external proxy, browser extension, telemetry agent, or unverified model downloader as a scope change requiring security review.
