export type Disposition = "ACCEPT" | "REVIEW" | "QUARANTINE";
export type CoverageState = "ASSESSED" | "PARTIALLY_ASSESSED" | "NOT_ASSESSED" | "FAILED_TO_EXECUTE" | "UNSUPPORTED";

export interface EvidenceRecord { id: string; kind: string; title: string; summary: string; data?: Record<string, unknown> | null; blob?: { digest: string; media_type: string; size_bytes: number } | null; }
export interface FindingRecord { id: string; title: string; reason: string; detector_id: string; attack_class: string; severity: string; confidence: number; recommended_disposition: Disposition; asset_id: string; affected_count?: number; evidence: EvidenceRecord[]; limitations?: string[]; access_assumptions?: string[]; policy_rule?: string; created_at?: string; }
export interface CoverageRecord { attack_class: string; layer: string; title: string; state: CoverageState; detectors: string[]; reason: string; required_access?: string[]; recommended_evidence?: string[]; }
export interface ExecutionRecord { detector_id: string; title: string; layer: string; state: string; planned: string; mode?: string | null; runtime_ms?: number; samples_processed?: number; findings?: number; reasons?: string[]; }
export interface AssetRecord { role: string; asset_id: string; name: string; format?: string | null; digest?: string | null; details?: Record<string, unknown>; }
export interface EventRecord { seq: number; t_ms: number; level: string; message: string; detector_id?: string | null; }

export interface WorkspaceScan {
  scan_id: string; name: string; profile: string; budget: string; status: string; created_at: string; completed_at?: string | null;
  findings: FindingRecord[]; coverage: { rows: CoverageRecord[]; total: number; assessed: number; partial: number; not_assessed: number; failed: number; unsupported: number };
  executions: ExecutionRecord[]; assets: AssetRecord[]; events: EventRecord[];
  capabilities?: { capability: string; present: boolean; withheld?: boolean; note?: string | null }[];
  summary?: { overall_disposition: Disposition; detectors_completed: number; detectors_degraded: number; detectors_unavailable: number; detectors_error: number } | null;
  report_digest?: string | null; source: "imported" | "server";
}

export const emptyWorkspaceScan: WorkspaceScan = {
  scan_id: "", name: "No assessment selected", profile: "", budget: "", status: "", created_at: "", completed_at: null,
  findings: [], coverage: { rows: [], total: 0, assessed: 0, partial: 0, not_assessed: 0, failed: 0, unsupported: 0 },
  executions: [], assets: [], events: [], source: "server",
};

export function parseReport(text: string, source: WorkspaceScan["source"] = "imported"): WorkspaceScan {
  const document: unknown = JSON.parse(text);
  if (!document || typeof document !== "object") throw new Error("This file is not a VisionX report.");
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
