import { parseReport } from "./workspace-data";
import type { WorkspaceScan } from "./workspace-data";

export interface ApiSession {
  user: { username: string; display_name: string; role: string };
  csrf: string;
  demo_mode?: boolean;
  version?: string;
}

export interface ApiAsset {
  id: string;
  kind: string;
  name: string;
}

export interface ApiProfile {
  name: string;
  description: string;
  budget: string;
}

interface ScanSummary {
  id: string;
  name: string;
  status: string;
  profile: string;
  created_at: string;
  completed_at: string | null;
  overall_disposition: "ACCEPT" | "REVIEW" | "QUARANTINE" | null;
  coverage: { assessed: number; partial: number; total: number };
  report_digest: string | null;
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  headers.set("X-VisionX-Demo", "1");
  return fetch(path, { credentials: "same-origin", cache: "no-store", ...init, headers });
}

async function errorText(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body.detail ?? body.error ?? `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export async function discoverApi(): Promise<boolean> {
  try {
    const response = await request("/api/system/info");
    if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) return false;
    const body = await response.json();
    return body.product === "VisionX";
  } catch { return false; }
}

export async function currentSession(): Promise<ApiSession | null> {
  const response = await request("/api/auth/me");
  if (response.status === 401) return null;
  if (!response.ok) throw new Error(await errorText(response));
  return response.json();
}

export async function login(username: string, password: string): Promise<ApiSession> {
  const response = await request("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
  if (!response.ok) throw new Error(await errorText(response));
  return response.json();
}

export async function logout(csrf: string): Promise<void> {
  const response = await request("/api/auth/logout", { method: "POST", headers: { "x-csrf-token": csrf } });
  if (!response.ok) throw new Error(await errorText(response));
}

export async function loadServerScans(): Promise<WorkspaceScan[]> {
  const response = await request("/api/scans?limit=30");
  if (!response.ok) throw new Error(await errorText(response));
  const list = await response.json() as { scans: ScanSummary[] };
  return Promise.all(list.scans.map(async item => {
    try {
      const report = await request(`/api/scans/${encodeURIComponent(item.id)}/report.json`);
      if (report.ok) return parseReport(await report.text(), "server");
    } catch { /* A pending scan has no report yet. */ }
    return {
      scan_id: item.id, name: item.name, profile: item.profile, budget: "—", status: item.status,
      created_at: item.created_at, completed_at: item.completed_at, source: "server", report_digest: item.report_digest,
      findings: [], executions: [], assets: [], events: [],
      coverage: { rows: [], total: item.coverage.total, assessed: item.coverage.assessed, partial: item.coverage.partial, not_assessed: 0, failed: 0, unsupported: 0 },
      summary: item.overall_disposition ? { overall_disposition: item.overall_disposition, detectors_completed: 0, detectors_degraded: 0, detectors_unavailable: 0, detectors_error: 0 } : null,
    } satisfies WorkspaceScan;
  }));
}

export async function loadServerAssets(): Promise<ApiAsset[]> {
  const response = await request("/api/assets?limit=200");
  if (!response.ok) throw new Error(await errorText(response));
  const body = await response.json() as { assets: ApiAsset[] };
  return body.assets;
}

export async function loadServerProfiles(): Promise<ApiProfile[]> {
  const response = await request("/api/system/profiles");
  if (!response.ok) throw new Error(await errorText(response));
  const body = await response.json() as { profiles: ApiProfile[] };
  return body.profiles;
}

export async function submitServerScan(body: { name: string; profile: string; dataset?: string; model?: string }, csrf: string): Promise<string> {
  const response = await request("/api/scans", { method: "POST", headers: { "Content-Type": "application/json", "x-csrf-token": csrf }, body: JSON.stringify(body) });
  if (!response.ok) throw new Error(await errorText(response));
  const data = await response.json() as { scan_id: string };
  return data.scan_id;
}
