# VisionX documentation

[Project README](../README.md) · [Current implementation](implementation-status.md) · [Readiness review](sih-readiness.md)

> **Choose your route through VisionX.** Start with a working assessment, trace the evidence, review the controls, or extend the platform. Each guide links to the implementation and the next step.

The handbook describes the current repository. Implemented features, recorded measurements, and work still required are distinguished throughout; no document is a blanket security or deployment certification.

<table>
<tr>
<td width="25%" valign="top">
<img src="images/navigation/first-run.svg" alt="Start with confidence" width="250" />
<h3>Start with confidence</h3>
<p>Install locally, understand an assessment, and review your first controlled scenario.</p>
<p><a href="handbook/01-getting-started.md">Getting started →</a><br><a href="handbook/03-workspace.md">Use the workspace →</a></p>
</td>
<td width="25%" valign="top">
<img src="images/navigation/inside-visionx.svg" alt="Understand the evidence" width="250" />
<h3>Understand the evidence</h3>
<p>Follow the architecture, detector plan, model access, provenance, and verification.</p>
<p><a href="handbook/04-architecture.md">Explore the architecture →</a><br><a href="handbook/06-detectors-and-profiles.md">Meet the detectors →</a></p>
</td>
<td width="25%" valign="top">
<img src="images/navigation/trust-control.svg" alt="Operate with proof" width="250" />
<h3>Operate with proof</h3>
<p>Review permissions, isolation, policy, configuration, and recovery procedures.</p>
<p><a href="handbook/09-security-governance.md">Review security →</a><br><a href="handbook/12-operations.md">Run operations →</a></p>
</td>
<td width="25%" valign="top">
<img src="images/navigation/build-ship.svg" alt="Build and present" width="250" />
<h3>Build and present</h3>
<p>Integrate with the API, extend the platform, and rehearse an evidence-led demonstration.</p>
<p><a href="handbook/13-development.md">Development guide →</a><br><a href="demo-script.md">Presenter script →</a></p>
</td>
</tr>
</table>

### The handbook · 15 connected guides

| Start using VisionX | Understand the system | Run it safely | Build on it |
| :--- | :--- | :--- | :--- |
| **[01 · Getting started](handbook/01-getting-started.md)**<br><sub>Install, provision, and run.</sub> | **[04 · Architecture](handbook/04-architecture.md)**<br><sub>Boundaries, state, and data flow.</sub> | **[09 · Security and governance](handbook/09-security-governance.md)**<br><sub>Access, isolation, and decisions.</sub> | **[13 · Development](handbook/13-development.md)**<br><sub>Test, contribute, and extend.</sub> |
| **[02 · Core concepts](handbook/02-core-concepts.md)**<br><sub>Assets, findings, and coverage.</sub> | **[05 · Data and models](handbook/05-data-and-models.md)**<br><sub>Formats, references, and intake.</sub> | **[10 · Configuration](handbook/10-configuration.md)**<br><sub>Profiles, limits, and environment.</sub> | **[14 · Demo guide](handbook/14-demo-guide.md)**<br><sub>Rehearse the full evidence route.</sub> |
| **[03 · Using the workspace](handbook/03-workspace.md)**<br><sub>Inspect, review, and approve.</sub> | **[06 · Detectors and profiles](handbook/06-detectors-and-profiles.md)**<br><sub>Prerequisites and execution.</sub> | **[11 · API reference](handbook/11-api-reference.md)**<br><sub>Endpoints, sessions, and jobs.</sub> | **[15 · FAQ and glossary](handbook/15-faq-and-glossary.md)**<br><sub>Precise terms and answers.</sub> |
| **[↳ Offline installation](offline-install.md)**<br><sub>Prepare and verify a transfer.</sub> | **[07 · Evidence and provenance](handbook/07-evidence-and-provenance.md)**<br><sub>Digests, chains, and trust.</sub> | **[12 · Operations](handbook/12-operations.md)**<br><sub>Back up, recover, and investigate.</sub> | **[↳ Script and judge answers](demo-script.md)**<br><sub>Speaking cues and fallbacks.</sub> |

**[08 · Verification and reproducibility](handbook/08-verification.md)** ties the four routes together: check the run, the report, the ledger, and the evaluation.

## Judge, review, and ship

| See the working system | Run the presentation | Assess readiness | Plan the build |
| :--- | :--- | :--- | :--- |
| **[Implementation status](implementation-status.md)**<br>Capabilities, source evidence, and current boundaries. | **[Demo script and answers](demo-script.md)**<br>A timed route with expected observations and fallbacks. | **[SIH readiness review](sih-readiness.md)**<br>Available evidence, gaps, and submission gates. | **[Build and submission plan](build-plan.md)**<br>Priorities, deliverables, and acceptance evidence. |

<p align="center"><sub><b>Security review route</b> · <a href="threat-model.md">Threat model</a> · <a href="handbook/09-security-governance.md#sandbox-and-offline-controls">Sandbox</a> · <a href="handbook/09-security-governance.md#audit-trail">Audit trail</a> · <a href="handbook/09-security-governance.md#security-review-route">Security tests</a> · <a href="handbook/08-verification.md">Signed evidence</a> · <a href="README.md">Handbook home</a></sub></p>

## Detailed specifications

| Reference | Purpose |
| --- | --- |
| [Architecture decisions](../ARCHITECTURE_DECISIONS.md) | Design rationale, corrections, and explicit non-goals. |
| [Detector methodology](detector-methodology.md) | Analytical assumptions and evidence requirements. |
| [Provenance specification](provenance-spec.md) | Records, trust roots, checkpoints, and external anchors. |
| [Report format](report-format.md) | Bundle structure, signing, and verification paths. |
| [Evaluation protocol](evaluation.md) | Eligibility, metric units, and unavailable estimates. |
| [Air-gap operations](airgap.md) | Application and host/network boundaries. |
| [Operator checklist](operator-guide.md) | Concise review sequence and incident response. |
| [Known limitations](known-limitations.md) | Current scientific, platform, and packaging constraints. |
| [Screenshot provenance](images/screenshots/README.md) | How the published frontend images were captured. |

## Keeping this handbook current

Update the relevant guide when API fields, profiles, configuration defaults, report behavior, or UI flows change. Link claims to source or retained artifacts, keep examples free of credentials, and verify relative links before submission. Numbered guide pages include previous/next navigation; existing specification files remain the detailed references.
