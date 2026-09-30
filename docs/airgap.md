# Air-gap operations

[Documentation home](README.md) · [Offline installation](offline-install.md) · [Security handbook](handbook/09-security-governance.md)

VisionX is designed to assess assets locally after dependencies and required models are provisioned. Offline operation has three separate boundaries: dependency preparation, application execution, and the host/network environment.

## Application controls

The workload guard pins offline library settings and intercepts selected Python socket/DNS operations to refuse nonlocal destinations. Supported native model paths use a constrained worker that attempts network namespace isolation and records available controls. Inspect the actual worker status; platform restrictions can reduce isolation.

```bash
visionsentinel selftest --airgap
```

Review individual checks, not just the printed summary. The self-test exercises selected network guards, cryptographic primitives, registry/profile integrity, and frontend references. It is not a host-wide packet capture or a guarantee against arbitrary native-code behavior.

## Host responsibilities

Prepare host firewall/network isolation, approved removable-media handling, browser configuration, and dependency custody appropriate to the environment. Other applications, extensions, proxies, and telemetry services are outside the Python guard. Record which controls were enforced and tested on the actual target.

The frontend and API communicate over loopback in the documented setup. Local communication is intentional. Do not confuse use of localhost with proof that every process on the host lacks external access.

## Transfer and recovery

Follow [offline installation](offline-install.md) to prepare checksummed dependencies and the checkout. The current container recipe needs frontend packaging alignment before use. Retain trust roots and ledger anchors independently; preserve the workspace coherently and rehearse recovery using [operations](handbook/12-operations.md).
