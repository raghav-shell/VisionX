export type Disposition = "ACCEPT" | "REVIEW" | "QUARANTINE";
export type CoverageState = "ASSESSED" | "PARTIALLY_ASSESSED" | "NOT_ASSESSED" | "FAILED_TO_EXECUTE" | "UNSUPPORTED";

export interface EvidenceRecord {
  id: string;
  kind: string;
  title: string;
  summary: string;
  data?: Record<string, unknown> | null;
  blob?: { digest: string; media_type: string; size_bytes: number } | null;
}

export interface FindingRecord {
  id: string;
  title: string;
  reason: string;
  detector_id: string;
  attack_class: string;
  severity: string;
  confidence: number;
  recommended_disposition: Disposition;
  asset_id: string;
  affected_count?: number;
  evidence: EvidenceRecord[];
  limitations?: string[];
  access_assumptions?: string[];
  policy_rule?: string;
  created_at?: string;
}

export interface CoverageRecord {
  attack_class: string;
  layer: string;
  title: string;
  state: CoverageState;
  detectors: string[];
  reason: string;
  required_access?: string[];
  recommended_evidence?: string[];
}

export interface ExecutionRecord {
  detector_id: string;
  title: string;
  layer: string;
  state: string;
  planned: string;
  mode?: string | null;
  runtime_ms?: number;
  samples_processed?: number;
  findings?: number;
  reasons?: string[];
}

export interface AssetRecord {
  role: string;
  asset_id: string;
  name: string;
  format?: string | null;
  digest?: string | null;
  details?: Record<string, unknown>;
}

export interface EventRecord {
  seq: number;
  t_ms: number;
  level: string;
  message: string;
  detector_id?: string | null;
}

export interface WorkspaceScan {
  scan_id: string;
  name: string;
  profile: string;
  budget: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
  findings: FindingRecord[];
  coverage: { rows: CoverageRecord[]; total: number; assessed: number; partial: number; not_assessed: number; failed: number; unsupported: number };
  executions: ExecutionRecord[];
  assets: AssetRecord[];
  events: EventRecord[];
  capabilities?: { capability: string; present: boolean; withheld?: boolean; note?: string | null }[];
  summary?: { overall_disposition: Disposition; detectors_completed: number; detectors_degraded: number; detectors_unavailable: number; detectors_error: number } | null;
  report_digest?: string | null;
  source: "example" | "imported" | "server";
}

const exampleCoverage: CoverageRecord[] = [
  { attack_class: "model.backdoor", layer: "MODEL", title: "Model backdoor indicators", state: "PARTIALLY_ASSESSED", detectors: ["model.neural_cleanse", "model.strip"], reason: "Available probes can surface some trigger patterns; dynamic and clean-label backdoors remain outside this assessment.", recommended_evidence: ["A trusted clean reference model", "Additional suspect inputs"] },
  { attack_class: "model.artifact_tamper", layer: "MODEL", title: "Artifact identity", state: "ASSESSED", detectors: ["model.artifact_digest"], reason: "Candidate artifact digest was compared with the approved identity." },
  { attack_class: "data.trigger_artifact", layer: "DATA", title: "Trigger artifacts", state: "ASSESSED", detectors: ["data.trigger_artifact"], reason: "Visible patch and frequency residual checks completed over accessible samples." },
  { attack_class: "data.label_noise", layer: "DATA", title: "Label integrity", state: "PARTIALLY_ASSESSED", detectors: ["data.label_consistency"], reason: "Labels were available, but no trusted adjudicated baseline was supplied." },
  { attack_class: "drift.covariate", layer: "DRIFT", title: "Input distribution shift", state: "NOT_ASSESSED", detectors: [], reason: "No operational batch was supplied for comparison.", required_access: ["OPERATIONAL_DATA", "REFERENCE_DATASET"] },
  { attack_class: "provenance.ledger_integrity", layer: "PROVENANCE", title: "Inference ledger integrity", state: "NOT_ASSESSED", detectors: [], reason: "No inference ledger or trust root was supplied.", required_access: ["INFERENCE_LEDGER", "LEDGER_TRUST_ROOT"] },
];

const exampleFindings: FindingRecord[] = [
  { id: "VX-104", title: "Concentrated patch response in one output class", reason: "The reconstructed trigger increased the target-class response across 31 of 40 probe images; the other classes stayed near their baseline response.", detector_id: "model.neural_cleanse", attack_class: "model.backdoor", severity: "HIGH", confidence: 0.81, recommended_disposition: "QUARANTINE", asset_id: "model-candidate", affected_count: 31, policy_rule: "model-trigger-review", evidence: [{ id: "ev-104", kind: "STATISTIC", title: "Probe response comparison", summary: "Target-class response against the remaining class baselines.", data: { probe_images: 40, target_responses: 31, target_class: "class-4" } }], limitations: ["This is an indicator, not a proof of a backdoor.", "Dynamic and clean-label triggers are not covered."], access_assumptions: ["MODEL_GRADIENTS", "PROBE_DATASET"] },
  { id: "VX-105", title: "Repeated corner artifact in contributor batch", reason: "A recurring high-frequency corner pattern appeared in 27 of 640 images from the same contributor batch, compared with 2 of 1,920 reference images.", detector_id: "data.trigger_artifact", attack_class: "data.trigger_artifact", severity: "MEDIUM", confidence: 0.74, recommended_disposition: "REVIEW", asset_id: "dataset-candidate", affected_count: 27, policy_rule: "artifact-triage", evidence: [{ id: "ev-105", kind: "TABLE", title: "Batch comparison", summary: "Pattern prevalence by source batch.", data: { candidate: "27 / 640", reference: "2 / 1,920" } }], limitations: ["Compression and acquisition artifacts may produce similar patterns."] },
];

export const exampleScans: WorkspaceScan[] = [
  {
    scan_id: "demo-model-001", name: "Candidate model review", profile: "strict", budget: "DEEP", status: "SEALED", created_at: "2026-09-24T10:30:00Z", completed_at: "2026-09-24T10:34:12Z", source: "example", report_digest: null,
    findings: exampleFindings,
    coverage: { rows: exampleCoverage, total: 6, assessed: 2, partial: 2, not_assessed: 2, failed: 0, unsupported: 0 },
    executions: [
      { detector_id: "model.artifact_digest", title: "Artifact digest", layer: "MODEL", state: "COMPLETED", planned: "READY", mode: "digest", runtime_ms: 41, findings: 0 },
      { detector_id: "model.neural_cleanse", title: "Neural Cleanse", layer: "MODEL", state: "COMPLETED_DEGRADED", planned: "DEGRADED", mode: "probe", runtime_ms: 7880, samples_processed: 40, findings: 1 },
      { detector_id: "data.trigger_artifact", title: "Trigger artifact analysis", layer: "DATA", state: "COMPLETED", planned: "READY", mode: "image", runtime_ms: 2144, samples_processed: 2560, findings: 1 },
      { detector_id: "drift.covariate", title: "Covariate drift", layer: "DRIFT", state: "NOT_RUN", planned: "UNAVAILABLE", reasons: ["Operational data was not supplied."], findings: 0 },
      { detector_id: "provenance.ledger_integrity", title: "Ledger integrity", layer: "PROVENANCE", state: "NOT_RUN", planned: "UNAVAILABLE", reasons: ["Inference ledger and trust root were not supplied."], findings: 0 },
    ],
    assets: [
      { role: "MODEL", asset_id: "model-candidate", name: "candidate_vit.onnx", format: "ONNX", digest: "sha256:8e72c1b45697a3d04f8ac316205f45c60bd39e719a24337db2cf9e841a60a1c7" },
      { role: "DATASET", asset_id: "dataset-candidate", name: "contributor_batch_coco", format: "COCO", details: { samples: 2560, contributors: 4 } },
      { role: "PROBE_DATASET", asset_id: "probe-set", name: "validation_probes", format: "ImageFolder", details: { samples: 40 } },
    ],
    events: [
      { seq: 1, t_ms: 0, level: "stage", message: "Assets probed and capabilities recorded." },
      { seq: 2, t_ms: 105, level: "stage", message: "Detector plan persisted before execution." },
      { seq: 3, t_ms: 2510, level: "warn", message: "Trigger artifact requires analyst review.", detector_id: "data.trigger_artifact" },
      { seq: 4, t_ms: 10380, level: "warn", message: "Model probe raised a backdoor indicator.", detector_id: "model.neural_cleanse" },
      { seq: 5, t_ms: 10420, level: "info", message: "Coverage and report assembled." },
    ],
    summary: { overall_disposition: "QUARANTINE", detectors_completed: 2, detectors_degraded: 1, detectors_unavailable: 2, detectors_error: 0 },
  },
  {
    scan_id: "demo-drift-002", name: "Incoming batch comparison", profile: "baseline", budget: "STANDARD", status: "SEALED", created_at: "2026-09-22T08:15:00Z", completed_at: "2026-09-22T08:18:05Z", source: "example", report_digest: null,
    findings: [{ id: "VX-201", title: "Image sharpness distribution shifted", reason: "The incoming batch showed lower edge-energy than the reference set across three sampled acquisition groups.", detector_id: "drift.covariate", attack_class: "drift.covariate", severity: "MEDIUM", confidence: 0.69, recommended_disposition: "REVIEW", asset_id: "incoming-batch", affected_count: 480, evidence: [{ id: "ev-201", kind: "DISTRIBUTION", title: "Sharpness shift", summary: "Reference and incoming edge-energy distributions by acquisition group." }], limitations: ["Distribution shift alone does not establish malicious manipulation."] }],
    coverage: { rows: [
      { attack_class: "drift.covariate", layer: "DRIFT", title: "Input distribution shift", state: "ASSESSED", detectors: ["drift.covariate"], reason: "Reference and incoming image distributions were compared." },
      { attack_class: "drift.semantic", layer: "DRIFT", title: "Semantic distribution shift", state: "PARTIALLY_ASSESSED", detectors: ["drift.semantic"], reason: "Embedding comparison completed without a calibrated semantic encoder." },
      { attack_class: "provenance.ledger_integrity", layer: "PROVENANCE", title: "Inference ledger integrity", state: "NOT_ASSESSED", detectors: [], reason: "No ledger was supplied." },
    ], total: 3, assessed: 1, partial: 1, not_assessed: 1, failed: 0, unsupported: 0 },
    executions: [
      { detector_id: "drift.covariate", title: "Covariate drift", layer: "DRIFT", state: "COMPLETED", planned: "READY", mode: "image", runtime_ms: 1602, findings: 1 },
      { detector_id: "drift.semantic", title: "Semantic drift", layer: "DRIFT", state: "COMPLETED_DEGRADED", planned: "DEGRADED", mode: "embedding", runtime_ms: 980, findings: 0 },
    ],
    assets: [
      { role: "REFERENCE_DATASET", asset_id: "reference-batch", name: "reference_images", format: "ImageFolder", details: { samples: 1200 } },
      { role: "OPERATIONAL_DATA", asset_id: "incoming-batch", name: "incoming_sep_22", format: "ImageFolder", details: { samples: 480 } },
    ],
    events: [{ seq: 1, t_ms: 0, level: "stage", message: "Reference and incoming batches loaded." }, { seq: 2, t_ms: 1602, level: "warn", message: "Sharpness distribution shift flagged for review.", detector_id: "drift.covariate" }],
    summary: { overall_disposition: "REVIEW", detectors_completed: 1, detectors_degraded: 1, detectors_unavailable: 0, detectors_error: 0 },
  },
];

export function parseReport(text: string, source: WorkspaceScan["source"] = "imported"): WorkspaceScan {
  const document: unknown = JSON.parse(text);
  if (!document || typeof document !== "object") throw new Error("This file is not a VisionSentinel report.");
  const envelope = document as Record<string, unknown>;
  if (envelope.schema && envelope.schema !== "visionsentinel/report/v1") throw new Error("Unsupported report schema.");
  const result = (envelope.result ?? envelope) as Partial<WorkspaceScan>;
  const record = (value: unknown): value is Record<string, unknown> => Boolean(value && typeof value === "object" && !Array.isArray(value));
  if (!record(result) || typeof result.scan_id !== "string" || typeof result.name !== "string" || !Array.isArray(result.findings) || !Array.isArray(result.coverage?.rows) || !Array.isArray(result.executions) || !Array.isArray(result.assets) ||
      !result.findings.every(item => record(item) && typeof item.id === "string" && typeof item.title === "string" && typeof item.reason === "string" && typeof item.detector_id === "string" && Array.isArray(item.evidence) && item.evidence.every(e => record(e) && typeof e.id === "string" && typeof e.title === "string" && typeof e.summary === "string")) ||
      !result.coverage.rows.every(item => record(item) && typeof item.attack_class === "string" && typeof item.title === "string" && typeof item.reason === "string" && Array.isArray(item.detectors)) ||
      !result.executions.every(item => record(item) && typeof item.detector_id === "string" && typeof item.title === "string") ||
      !result.assets.every(item => record(item) && typeof item.asset_id === "string" && typeof item.name === "string")) {
    throw new Error("The file is missing required scan result fields.");
  }
  return { ...result, source, events: Array.isArray(result.events) ? result.events : [], findings: result.findings, assets: result.assets, executions: result.executions, coverage: result.coverage!, profile: result.profile ?? "unknown", budget: result.budget ?? "unknown", status: result.status ?? "unknown", created_at: result.created_at ?? "" } as WorkspaceScan;
}
