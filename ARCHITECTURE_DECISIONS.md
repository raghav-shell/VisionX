# VisionSentinel — Architecture Decisions

**Status:** accepted · **Scope:** SIH26228 — Trustworthy Computer Vision Integrity Assurance for Data, Models and Inference Outputs in Multi-Contributor Pipelines

This document records the decisions that shape VisionSentinel, why each was taken, and which
alternatives were rejected. It is the contract that the code, the tests and the documentation are
held to. Where the original product brief contained an assumption that turned out to be wrong or
needlessly complex, the correction is written down explicitly in §16 ("Design corrections").

---

## 1. System boundaries

VisionSentinel is an **offline assurance workstation**. It never trains production models, never
serves production inference, and never calls out to a network. It *assesses* artifacts that other
systems produced and *records* evidence about them.

```text
                         ┌────────────────────── TRUST BOUNDARY: air-gapped host ──────────────────────┐
 untrusted inputs        │                                                                              │
 ───────────────►        │  loaders (size/path/format limits) ──► sandboxed model worker (rlimits,     │
 datasets (zip/dir)      │                                          audit-hook: no sockets/exec)        │
 model files             │           │                                          │                       │
 inference ledgers       │           ▼                                          ▼                       │
 operational batches     │   assurance engines (data · model · provenance · drift) ──► evidence store  │
                         │           │                                    (content-addressed, sha256)   │
                         │           ▼                                                                  │
                         │   risk engine (policy + guardrails) ──► report sealed (Ed25519)             │
                         │           │                                                                  │
                         │   API (FastAPI, same-origin, CSRF, RBAC) ◄──► dashboard (static export)     │
                         │           │                                                                  │
                         │   governance (two-person rule) ──► audit ledger (hash chain + Ed25519)      │
                         └──────────────────────────────────────────────────────────────────────────────┘
 trusted inputs: trust root (public keys, approved model digests), profiles, calibration artifacts
```

In scope: integrity of training data, of models (identity, structure, behaviour, backdoor
indicators), of inference records (cryptographic provenance), and of operational input
distributions (drift and manipulation triage). Also in scope: the integrity of the assurance
process itself — what ran, what could not run, who decided what.

Out of scope (declared, surfaced in every coverage statement): adversarial-example robustness
certification, model extraction / membership inference, clean-label and input-aware dynamic
backdoors (no detector here is validated against them), physical-world triggers, and the security
of the host operating system.

## 2. Modules

The Python engine is **one distribution** (`visionsentinel`) whose sub-packages map one-to-one onto
the modules in the brief. The dashboard is a separate Next.js application that is compiled to static
files and served by the API on the same origin.

| Package | Responsibility | May import |
|---|---|---|
| `contracts` | Pydantic domain objects and enums (Finding, Evidence, Capability, DetectorSpec, Coverage, Report…) | stdlib, pydantic |
| `core` | detector registry, capability negotiation, scan planner, orchestrator, profiles, budgets, determinism, resource limits | contracts |
| `evidence` | content-addressed blob store, evidence builders (contact sheets, heatmaps), evidence graph | contracts, core |
| `vision` | image primitives shared by several engines: perceptual hashes, filters, image statistics, embedding encoders | contracts, core |
| `loaders` | safe file IO, dataset formats (COCO/YOLO/VOC/ImageFolder/manifest), model backends (ONNX, TorchScript, state-dict, safetensors), sandboxed worker, differentiable ONNX interpreter | contracts, core, vision |
| `data_assurance` | dataset detectors | contracts, core, evidence, vision, loaders |
| `model_assurance` | model detectors, probe battery | ↑ |
| `drift` | covariate/semantic drift, drift-vs-manipulation interpretation | ↑ |
| `provenance` | canonical JSON, Ed25519 ledger, Merkle checkpoints, trust root, standalone verifier, inference recorder | contracts (verifier: stdlib + `cryptography` only) |
| `risk` | policy engine, guardrails, calibration, contributor risk, coverage computation | contracts, core |
| `reporting` | report.json / report.html / coverage.md / manifest.json, scan comparison | contracts, core, evidence, risk |
| `governance` | roles, decision workflow, two-person rule, audit trail | contracts, provenance, storage |
| `storage` | SQLAlchemy models and repositories (SQLite default) | contracts |
| `attacklab` | synthetic corpus, reproducible attack generators, scenario manifests, fitness gates, demo builder | everything below API |
| `evaluation` | benchmark runner, TPR/FPR/AUROC with intervals, calibration/evaluation family split | attacklab, risk |
| `api` | FastAPI app, auth, CSRF, rate limiting, SSE, static dashboard serving | everything |
| `cli` | `visionsentinel` command | everything |

Layering is enforced by `tests/unit/test_architecture.py`, which parses imports and fails when a
lower layer imports a higher one (e.g. `contracts` importing `core`, or the verifier importing
anything beyond the standard library and `cryptography`).

## 3. Domain contracts

All contracts are Pydantic v2 models with `extra="forbid"` and are exported as JSON Schema into
`schemas/`. The central objects:

* **Capability** — a unit of access (`DATASET_IMAGES`, `MODEL_GRADIENTS`, `INFERENCE_LEDGER`, …).
* **DetectorSpec** — static declaration of a detector: id, version, category, required/optional
  capabilities, supported attack classes with support level (FULL/PARTIAL), explicitly
  unsupported attack classes with reasons, runtime class, minimum budget tier, evidence kinds,
  known limitations, access assumptions, determinism, calibration requirement, references.
* **Negotiation** — per-scan result of matching a DetectorSpec to the probed capabilities:
  `READY | DEGRADED | UNAVAILABLE | BUDGET_EXCLUDED`, the selected mode, missing capabilities and
  human-readable reasons.
* **DetectorExecution** — what actually happened: planned availability, final state
  (`COMPLETED | COMPLETED_DEGRADED | ABSTAINED | NOT_RUN | ERROR`), runtime, samples processed, peak
  memory estimate, error class/message. `ERROR` is never folded into `UNAVAILABLE`.
* **Finding** — id, scan, detector id+version, asset type/id, attack class, severity, confidence,
  raw score, threshold, title, *reason* (a sentence stating the observation), evidence references,
  access assumptions, limitations, recommended disposition, availability, the policy rule that set
  the disposition, affected samples/contributors, calibration status, creation time.
* **Evidence** — typed, titled, summarised; small data inline, large blobs referenced by sha256.
* **CoverageRow** — per attack class: `ASSESSED | PARTIALLY_ASSESSED | NOT_ASSESSED |
  FAILED_TO_EXECUTE | UNSUPPORTED`, contributing detectors, reason, required access, recommended
  additional evidence. Coverage is *computed*, never typed by hand.

Finding reasons are written evidence-first: the sentence names the observation, the counts and the
comparison baseline; numbers such as `raw_score` and `confidence` are separate fields.

## 4. Capability model

1. **Probe.** Each supplied asset is opened by its loader, which reports the capabilities it can
   actually provide (e.g. an ONNX file whose ops are all supported by the differentiable
   interpreter *and* whose interpreter output matches onnxruntime within tolerance yields
   `MODEL_GRADIENTS` and `MODEL_ACTIVATIONS`; a model with an unsupported op yields only
   `MODEL_PREDICT`/`MODEL_LOGITS`).
2. **Restrict.** The profile may deny capabilities (`blackbox.yaml` denies graph, parameters,
   activations and gradients) to reproduce a vendor black-box engagement. Denied capabilities are
   reported as *withheld by policy*, distinct from *not present*.
3. **Negotiate.** Every registered detector is negotiated. Missing required capability →
   `UNAVAILABLE`; missing optional capability that changes the method → `DEGRADED` with the mode
   named; detector minimum budget above the profile budget → `BUDGET_EXCLUDED`; a detector may also
   declare scientific preconditions (e.g. Neural Cleanse needs ≥ 5 classes) that produce
   `UNAVAILABLE` with the precondition stated.
4. **Plan.** The plan (all registered detectors, none silently dropped) is persisted *before*
   execution and shown to the operator.
5. **Execute.** Detectors run in dependency order. An exception becomes `ERROR` with the exception
   class and message; dependants of a failed detector become `ERROR` ("upstream detector failed"),
   never `UNAVAILABLE`. A detector that runs but finds its data insufficient (e.g. fewer than 30
   samples in every class) returns `ABSTAINED` with the reason.

## 5. Detector plugin contract

```python
class Detector(Protocol):
    spec: ClassVar[DetectorSpec]
    Params: ClassVar[type[BaseModel]]          # extra="forbid"; profile values validated here

    def negotiate(self, caps: CapabilitySet, ctx: PlanContext) -> Negotiation: ...
    def run(self, ctx: ScanContext) -> DetectorResult: ...
```

`DetectorResult` carries candidate findings (the detector proposes severity/confidence; the risk
engine sets the final disposition), evidence, metrics, per-sample flags for contributor analysis,
and the attack classes actually assessed in the chosen mode. Registration is explicit (a static
list in `core/registry.py` populated by each engine's `register()`), so a scan can always prove the
complete set of detectors that exist.

## 6. Risk architecture

```text
Finding (detector proposal) → evidence confidence → calibration status → attack class
        → policy rule (first match, from profile) → guardrails (non-overridable) → disposition
```

* Policies are ordered rules in the profile. The matching rule id and the policy digest are stored
  on every finding.
* Guardrails run after the policy and cannot be configured away:
  cryptographic integrity failure ⇒ never `ACCEPT`; uncalibrated statistical detector ⇒ at most
  `REVIEW`; metadata-only evidence ⇒ at most `REVIEW`; drift-manipulation inference ⇒ at most
  `REVIEW` unless ≥ 3 independent corroborating signals; findings from `DEGRADED` executions carry
  capped confidence.
* There is no global "security score". The top-level numbers are counts of findings by disposition
  and *assessment coverage* (share of attack classes fully assessed).
* **Contributor risk** is a Beta–Binomial model: prior centred on the median of the other
  contributors' flag rates with profile-defined strength, posterior over the contributor's flag rate, posterior probability
  that the rate exceeds the baseline by a factor, posterior-predictive expected-flag interval, and
  campaign-level findings (systematic mislabel, trigger correlation, duplicate flood) attributed to
  the contributor. Small contributors are shrunk towards the baseline instead of being ranked on a
  raw ratio.

## 7. Evidence model

* Evidence blobs (PNG contact sheets, heatmaps, JSON tables) are written to
  `var/evidence/sha256/<aa>/<digest>` and referenced by digest. Every read re-hashes the blob; a
  mismatch raises `EvidenceIntegrityError` and is shown as tampered evidence.
* Only formats VisionSentinel generates itself are stored as blobs (PNG, JSON). User-controlled text
  is never rendered as HTML; SVG/HTML are never accepted as evidence.
* The **evidence graph** links Contributor → Sample → Detector → Finding → Evidence, Model →
  InferenceRecord, Finding → Decision → User, stored as node/edge lists inside the scan result and
  in relational tables — no graph database.

## 8. Provenance model

* **Canonical form:** a JCS-compatible (RFC 8785) serializer restricted to objects, arrays, strings,
  integers, booleans and null. Floats are rejected in signed payloads; scores are stored as decimal
  strings so that canonical bytes are unambiguous across languages.
* **Record:** `{v, ledger_id, seq, prev, ts, nonce, kind, body, key_id}` + `sig`. For inference
  records the body binds input digest, model artifact digest, preprocessing-config digest,
  inference-config digest, software version, output and output digest.
* **Signature:** Ed25519 (via `cryptography`) over a domain-separated message
  `b"visionsentinel/ledger/v1\0" || canonical(record without sig)`.
* **Chain:** `entry_hash = SHA-256(b"visionsentinel/entry/v1\0" || canonical(record with sig))`;
  `record[i].prev = entry_hash(record[i-1])`; the header record (seq 0) is the genesis.
* **Checkpoints:** RFC 6962-style Merkle tree (0x00 leaf / 0x01 node prefixes) over entry hashes;
  signed checkpoint records are written in-ledger and exported to an external anchor file that the
  operator keeps elsewhere. Anchors detect truncation and history rewriting.
* **Verifier:** `visionsentinel verify` and `python -m visionsentinel.provenance.verifier` depend
  only on the standard library and `cryptography`. They report per record `VALID`, `FAILED(reason)`
  or `UNTRUSTED(chain continuity lost at seq N)`, plus replay (duplicate seq / nonce / entry),
  reorder, gap, truncation-against-anchor, unknown or revoked key, and binding violations against
  the trust root's approved models.
* **Audit ledger:** governance events use the same ledger machinery with `kind="audit"`.

## 9. Storage model

* SQLite (WAL mode) through SQLAlchemy 2.0 by default; the URL is configurable so PostgreSQL can be
  used without code changes. Tables: users, sessions, scans, scan_events, detector_executions,
  findings, contributors, decisions, audit_events, attack_runs.
* A scan's complete result is also persisted as a canonical JSON document in the evidence store; the
  report digest binds that document.
* Embedding and analysis caches: `var/cache/<kind>/<sha256(dataset digest ‖ encoder digest ‖
  preprocess digest)>.npy`, loaded with `allow_pickle=False`.

## 10. API boundaries

REST under `/api` (JSON only) plus SSE at `/api/scans/{id}/events`. The dashboard is a static
export served from the same origin, so cookies are `SameSite=Strict` and no CORS is enabled. The API
accepts **asset identifiers**, never file-system paths: assets enter the workspace through the CLI
(`visionsentinel assets import`) or through size-limited uploads with safe archive extraction. The
attack lab endpoint accepts only identifiers of scenarios shipped in `scenarios/`.

## 11. Security boundaries

| Boundary | Control |
|---|---|
| Untrusted archives | member path normalisation, no absolute paths / `..` / symlinks / devices, member count and total-size limits, compression-ratio limit |
| Untrusted images | header-only dimension check before decode, `MAX_IMAGE_PIXELS`, format allow-list (PNG/JPEG/BMP/TIFF/WebP), no SVG |
| Untrusted XML (VOC) | `defusedxml` (no DTD, no entities, no external references) |
| Untrusted JSON (COCO, manifests) | byte-size limit before parse, depth limit, element-count limits |
| Untrusted models | size limit; ONNX parsed without external data (external references rejected); native runtimes (onnxruntime, TorchScript, `torch.load(weights_only=True)`) execute only inside a spawned worker with `RLIMIT_AS`/`RLIMIT_CPU`, an audit hook that denies sockets, subprocesses and file writes, and a pickle-free (`.npy`, `allow_pickle=False`) result channel; tensor allocations bounded before execution |
| Web | CSP with per-page script hashes, CSRF token + Origin check, `SameSite=Strict` HttpOnly cookies, trusted hosts, rate limits, RBAC dependency on every route, `nosniff`, `frame-ancestors 'none'`, upload limits |
| Credentials | Argon2id (argon2-cffi); scrypt fallback; never plain hashes |
| Reports | every user- or evidence-derived string HTML-escaped; report HTML is self-contained with a restrictive CSP meta tag |
| Command execution | no `shell=True`, no string-built commands anywhere (enforced by a test that scans the source tree) |

## 12. Air-gap strategy

* No runtime code path imports an HTTP client. `tests/security/test_airgap.py` installs a socket
  guard (connect, `create_connection`, `getaddrinfo`) that fails on any non-loopback address while
  running full scans, the API and the attack lab.
* `visionsentinel selftest --airgap` repeats that guarded run and statically scans the package and
  the built dashboard for external origins (script/style/font/`fetch` targets).
* Fonts (IBM Plex via `@fontsource`), icons and charts are bundled. `NEXT_TELEMETRY_DISABLED=1`.
* Foundation encoders are optional and loaded only from `assets/models/` after SHA-256 verification;
  `scripts/vendor_models.py` is the only code that downloads anything and is not importable by the
  runtime. `HF_HUB_OFFLINE=1` and `TORCH_HOME` are pinned at start-up as defence in depth.

## 13. Testing strategy

Tests assert **invariants**, not implementation details. Categories:

* `unit` — contracts, registry, negotiation, statistics, canonical JSON, Merkle, each detector.
* `integration` — full scans on generated corpora, API flows, CLI.
* `security` — archive traversal, XXE, oversized JSON, decompression bombs, malicious filenames,
  unsafe model loading, HTML/SVG injection in reports, CSRF, RBAC bypass, host-header abuse, egress.
* `scientific` — clean vs attacked scenarios with explicit false-positive assertions.
* `regression` — determinism (same seed ⇒ same scenario and same findings), report schema stability.
* `e2e` — Playwright: login → scan → findings → decision request → second-user approval → ledger.

Invariants tested explicitly include: a detector requiring labels is never `READY` without labels;
an analyst never approves their own sensitive override; a report never reports an unavailable
class as assessed; a signature mismatch never yields `ACCEPT`; a black-box scan never claims
white-box checks ran; no registered detector is silently skipped; every finding names its evidence
or states that evidence is unavailable.

## 14. Scientific evaluation strategy

* Every scenario is generated from a manifest + seed and carries ground truth.
* **Fitness gates** reject invalid corpora before they enter a benchmark (e.g. backdoor scenarios
  must reach clean accuracy within [min, max] and attack success rate ≥ min).
* Thresholded detectors are **calibrated on calibration families** and **reported on held-out
  families** — never on the samples used to pick the threshold. Calibration artifacts record the
  source families, seeds and sizes; profiles reference them with `threshold_origin`.
* Reported metrics: TPR and FPR at the operating threshold with Wilson intervals, AUROC with
  bootstrap intervals where a continuous score exists, Brier score and reliability bins for
  calibrated probabilities.
* Detectors that fail their benchmark are reported as such and demoted in the documentation; the
  threshold is not re-tuned against the evaluation set.

## 15. Implementation phases

1. Foundation — contracts, capability system, registry, profiles, planner/orchestrator, evidence
   store, CLI skeleton.
2. Dataset loaders + security boundaries; synthetic corpus generator.
3. Data integrity detectors.
4. Trigger analysis and contributor risk.
5. Model loaders, sandbox, differentiable ONNX interpreter, capability probing.
6. Model identity: digest, architecture, weight statistics, behavioural fingerprint.
7. Advanced model assessment: activations, Neural Cleanse, STRIP, black-box stress suite.
8. Drift engine.
9. Provenance cryptography + standalone verifier.
10. Risk engine + calibration + coverage.
11. Reporting + scan comparison + evidence graph.
12. Backend API + storage.
13. Mission-control dashboard.
14. Governance.
15. Attack lab + demo corpus/models.
16. Evaluation and calibration runs.
17. Security hardening pass.
18. End-to-end demo polish.

## 16. Design corrections

**DC-1 — One Python distribution instead of twelve packages.**
*Original assumption:* each module under `packages/` is a separately installable package.
*Why it is incorrect:* the modules share one release cycle and one set of contracts; twelve
`pyproject.toml` files would add version-skew failure modes without adding isolation that the
interpreter enforces anyway. *Replacement:* one distribution with sub-packages named after the
modules and an import-layering test. *Impact:* `apps/api` and `apps/cli` become
`visionsentinel.api` and `visionsentinel.cli`; `apps/dashboard` remains a separate Next.js app.

**DC-2 — Coverage has five states, not four.**
*Original assumption:* ASSESSED / PARTIAL / NOT ASSESSED / FAILED.
*Why it is incomplete:* "no detector in this product addresses this attack" is a different
statement from "a detector exists but could not run here". *Replacement:* add `UNSUPPORTED`.
*Impact:* the coverage statement distinguishes product limitations from engagement limitations.

**DC-3 — Detectors propose, the risk engine disposes.**
*Original assumption:* each finding carries a recommended disposition from its detector.
*Why it is weak:* dispositions set inside detectors cannot be audited against a single policy.
*Replacement:* detectors emit severity/confidence proposals; dispositions come only from the
profile policy plus guardrails, and the rule id is stored on the finding.

**DC-4 — `ABSTAINED` is an execution state.**
*Original assumption:* availability states cover everything.
*Why it is incomplete:* a detector can be fully available yet discover at run time that the data do
not support a conclusion (e.g. classes too small). Reporting that as `UNAVAILABLE` would hide that
it ran; reporting it as `ERROR` would be false. *Replacement:* execution state `ABSTAINED` with a
reason; coverage treats it as `NOT_ASSESSED` for the affected classes.

**DC-5 — ONNX gradients through a verified interpreter.**
*Original assumption:* ONNX models are black-box for gradient methods.
*Why it is limiting:* ONNX graphs are data, not code. *Replacement:* a whitelisted-operator
PyTorch interpreter executes the graph differentiably; it is enabled only if its outputs match
onnxruntime on a probe batch within tolerance, otherwise `MODEL_GRADIENTS` is reported unavailable
with the fidelity error. *Impact:* Neural Cleanse and activation analysis are available for ONNX
models without executing untrusted code.

**DC-6 — Floats are banned from signed payloads.**
*Original assumption:* sign the JSON record.
*Why it is fragile:* float formatting differs across languages and versions, which makes
independent verification brittle. *Replacement:* JCS-compatible canonicalisation that rejects
floats; scores are decimal strings.

**DC-7 — Contributor ranking uses a robust leave-one-out baseline.**
*Original assumption:* compare each contributor with the population rate.
*Why it is biased:* a heavy attacker inflates the population rate and hides itself. A pooled
leave-one-out rate is not enough either: in the attack-lab corpus a second attacker (Delta, 45
flagged samples) raised the pooled baseline of the first (Charlie) to ~10 % and hid it.
*Replacement:* the prior for contributor *c* is centred on the **median** of the other
contributors' rates, which is unaffected by any minority of attackers.

**DC-8 — Demo corpus is procedurally generated.**
*Original assumption:* ship a small realistic dataset.
*Why:* redistributable real imagery with military classes is not available under a clear licence,
and a generator gives exact ground truth and seed-level reproducibility for every attack.
*Replacement:* a procedural overhead-reconnaissance chip generator (terrain textures, vehicle,
aircraft and vessel silhouettes, shadows, clutter, sensor noise, illumination). The documentation
states plainly that it is synthetic and that detector performance on it is not a claim about
operational imagery.
