import { parseReport } from "./workspace-data";
import type { WorkspaceScan } from "./workspace-data";

export interface ApiSession { user: { username: string; display_name: string; role: string }; csrf: string; demo_mode?: boolean; direct_demo?: boolean; version?: string }
export interface ApiAsset { id: string; kind: string; name: string; digest?: string | null; details?: Record<string, unknown>; lifecycle?: string; created_at?: string | null }
export interface ApiProfile { name: string; description: string; budget: string; digest?: string; withheld?: string[]; seed?: number }
export interface ApiMetadata {
  asset_kinds: { value: string; label: string }[];
  asset_lifecycles: string[];
  asset_inputs: { field: string; compatible_kinds: string[] }[];
  statuses: Record<string, string[]>;
  roles: { value: string; rank: number }[];
  governance: { reason_codes: string[]; protected_attack_classes: string[] };
  scan_events: { event: string; complete: string; unavailable: string };
  job_poll_interval_ms: number;
}
export interface ApiDecision { id: string; finding_id: string; scan_id: string; requested_by: string; requested_at: string | null; from_disposition: string; to_disposition: string; reason_code: string; justification: string; sensitive: boolean; status: string; decided_by?: string | null; decided_at?: string | null; decision_note?: string | null; current_disposition?: string | null }
export interface ApiFinding { finding_id: string; scan_id: string; detector_id: string; attack_class: string; layer: string; severity: string; original_disposition: string; disposition: string; deterministic: boolean; title: string; confidence: number; owner?: string | null; acknowledged_at?: string | null; acknowledged_by?: string | null; status: string; decisions: { pending: ApiDecision | null; latest: ApiDecision | null } }
export interface ApiFindingDetail { immutable: Record<string, unknown>; governance: { state: ApiFinding; decisions: { pending: ApiDecision | null; latest: ApiDecision | null } } }
export interface ApiHistoryEvent { id: number; timestamp: string | null; actor: string; action: string; old_state?: string | null; new_state?: string | null; reason_code?: string | null; justification?: string | null; ledger_seq?: number | null; entry_hash?: string | null }
export interface ApiScenario { scenario_id: string; title: string; description?: string; attack_class?: string; evaluation_family?: string; negative_control?: boolean; [key: string]: unknown }
export interface ApiJobStep { name?: string; detail?: string; status?: string; at?: string; [key: string]: unknown }
export interface ApiJob { id: string; kind: string; subject: string; status: string; terminal: boolean; started_by: string; started_at: string | null; completed_at: string | null; steps: ApiJobStep[]; scan_id: string | null; result: Record<string, unknown> | null; error: string | null }
export interface ApiGraphNode { id: string; type: string; label: string; attrs: Record<string, unknown> }
export interface ApiGraphEdge { source: string; target: string; type: string; attrs: Record<string, unknown> }
export interface ApiEvidenceGraph { nodes: ApiGraphNode[]; edges: ApiGraphEdge[] }

interface ScanSummary { id: string; name: string; status: string; profile: string; created_at: string; completed_at: string | null; overall_disposition: string | null; coverage: { assessed: number; partial: number; total: number }; report_digest: string | null }
export type ScanRequestBody = { name: string; profile: string; [field: string]: string | undefined };

async function request(path: string, init?: RequestInit): Promise<Response> {
  // The API is authoritative for authentication and demo access. Never send a
  // synthetic demo header from a real browser workspace.
  return fetch(path, { credentials: "same-origin", cache: "no-store", ...init });
}
async function errorText(response: Response): Promise<string> { try { const body = await response.json() as { detail?: string; error?: string }; return body.detail ?? body.error ?? `Request failed (${response.status})`; } catch { return `Request failed (${response.status})`; } }
async function json<T>(path: string, init?: RequestInit): Promise<T> { const response = await request(path, init); if (!response.ok) throw new Error(await errorText(response)); return response.json() as Promise<T>; }

export async function discoverApi(): Promise<boolean> { try { const response = await request("/api/system/info"); if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) return false; return (await response.json() as { product?: string }).product === "VisionX"; } catch { return false; } }
export async function currentSession(): Promise<ApiSession | null> { const response = await request("/api/auth/me"); if (response.status === 401) return null; if (!response.ok) throw new Error(await errorText(response)); return response.json(); }
export const loadMetadata = () => json<ApiMetadata>("/api/system/metadata");
export const login = (username: string, password: string) => json<ApiSession>("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
export async function logout(csrf: string): Promise<void> { await json("/api/auth/logout", { method: "POST", headers: { "x-csrf-token": csrf } }); }

export async function loadServerScans(): Promise<WorkspaceScan[]> {
  const list = await json<{ scans: ScanSummary[] }>("/api/scans?limit=30");
  return Promise.all(list.scans.map(async item => {
    try { const report = await request(`/api/scans/${encodeURIComponent(item.id)}/report.json`); if (report.ok) return parseReport(await report.text(), "server"); } catch { /* Pending or failed scans have no report yet. */ }
    return { scan_id: item.id, name: item.name, profile: item.profile, budget: "", status: item.status, created_at: item.created_at, completed_at: item.completed_at, source: "server", report_digest: item.report_digest, findings: [], executions: [], assets: [], events: [], coverage: { rows: [], total: item.coverage.total, assessed: item.coverage.assessed, partial: item.coverage.partial, not_assessed: 0, failed: 0, unsupported: 0 }, summary: item.overall_disposition ? { overall_disposition: item.overall_disposition as never, detectors_completed: 0, detectors_degraded: 0, detectors_unavailable: 0, detectors_error: 0 } : null } satisfies WorkspaceScan;
  }));
}
export const loadServerAssets = async () => (await json<{ assets: ApiAsset[] }>("/api/assets?limit=200")).assets;
export async function uploadServerAsset(file: File, kind: string, csrf: string): Promise<ApiAsset> {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("kind", kind);
  return json<ApiAsset>("/api/assets/upload", { method: "POST", headers: { "x-csrf-token": csrf }, body: form });
}
export const loadServerProfiles = async () => (await json<{ profiles: ApiProfile[] }>("/api/system/profiles")).profiles;
export async function submitServerScan(body: ScanRequestBody, csrf: string): Promise<string> { return (await json<{ scan_id: string }>("/api/scans", { method: "POST", headers: { "Content-Type": "application/json", "x-csrf-token": csrf }, body: JSON.stringify(body) })).scan_id; }
export const deleteServerScan = (scanId: string, csrf: string) => json<{ deleted: string }>(`/api/scans/${encodeURIComponent(scanId)}`, { method: "DELETE", headers: { "x-csrf-token": csrf } });

export const loadFinding = (id: string) => json<ApiFindingDetail>(`/api/findings/${encodeURIComponent(id)}`);
export const loadFindingHistory = (id: string) => json<{ finding_id: string; total: number; events: ApiHistoryEvent[] }>(`/api/findings/${encodeURIComponent(id)}/history`);
export const acknowledgeFinding = (id: string, csrf: string) => json<{ governance: { state: ApiFinding } }>(`/api/findings/${encodeURIComponent(id)}/acknowledge`, { method: "POST", headers: { "x-csrf-token": csrf } });
export const assignFinding = (id: string, owner: string, csrf: string) => json<{ governance: { state: ApiFinding } }>(`/api/findings/${encodeURIComponent(id)}/owner`, { method: "POST", headers: { "Content-Type": "application/json", "x-csrf-token": csrf }, body: JSON.stringify({ owner }) });
export const commentFinding = (id: string, text: string, csrf: string) => json<{ governance: { state: ApiFinding } }>(`/api/findings/${encodeURIComponent(id)}/comment`, { method: "POST", headers: { "Content-Type": "application/json", "x-csrf-token": csrf }, body: JSON.stringify({ text }) });
export const requestFindingDecision = (id: string, body: { target_disposition: string; reason_code: string; justification: string }, csrf: string) => json<ApiDecision>(`/api/findings/${encodeURIComponent(id)}/decision`, { method: "POST", headers: { "Content-Type": "application/json", "x-csrf-token": csrf }, body: JSON.stringify(body) });
export const decide = (id: string, action: "approve" | "reject", justification: string, csrf: string) => json<ApiDecision>(`/api/governance/decisions/${encodeURIComponent(id)}/${action}`, { method: "POST", headers: { "Content-Type": "application/json", "x-csrf-token": csrf }, body: JSON.stringify({ justification }) });
export const loadScenarios = async () => (await json<{ scenarios: ApiScenario[] }>("/api/attacklab/scenarios")).scenarios;
export const runScenario = (id: string, profile: string, csrf: string) => json<{ job_id: string; status: string }>(`/api/attacklab/scenarios/${encodeURIComponent(id)}/run`, { method: "POST", headers: { "Content-Type": "application/json", "x-csrf-token": csrf }, body: JSON.stringify({ profile }) });
export const loadJob = (id: string) => json<ApiJob>(`/api/jobs/${encodeURIComponent(id)}`);
export const loadScanGraph = (id: string) => json<ApiEvidenceGraph>(`/api/scans/${encodeURIComponent(id)}/graph`);

export function subscribeToScan(scanId: string, metadata: ApiMetadata, handlers: { event: (event: Record<string, unknown>) => void; complete: (event: Record<string, unknown>) => void; unavailable: (event: Record<string, unknown>) => void; error: () => void }): EventSource {
  const source = new EventSource(`/api/scans/${encodeURIComponent(scanId)}/events`, { withCredentials: true });
  const parse = (event: MessageEvent<string>) => { try { handlers.event(JSON.parse(event.data) as Record<string, unknown>); } catch { /* Ignore malformed frames. */ } };
  source.addEventListener(metadata.scan_events.event, parse);
  source.addEventListener(metadata.scan_events.complete, event => { parse(event as MessageEvent<string>); try { handlers.complete(JSON.parse((event as MessageEvent<string>).data) as Record<string, unknown>); } catch { handlers.error(); } });
  source.addEventListener(metadata.scan_events.unavailable, event => { parse(event as MessageEvent<string>); try { handlers.unavailable(JSON.parse((event as MessageEvent<string>).data) as Record<string, unknown>); } catch { handlers.error(); } });
  source.onerror = handlers.error;
  return source;
}
