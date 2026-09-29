export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let csrfToken: string | null = null;

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  csrf?: boolean;
};

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, csrf = false, ...init } = options;
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (body !== undefined) headers.set("Content-Type", "application/json");
  if (csrf && csrfToken) headers.set("X-CSRF-Token", csrfToken);

  const response = await fetch(path, {
    ...init,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
    headers,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string;
      error?: string;
    } | null;
    throw new ApiError(
      response.status,
      payload?.detail ??
        payload?.error ??
        `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}

export const api = {
  async upload<T>(path: string, form: FormData): Promise<T> {
    const headers = new Headers({ Accept: "application/json" });
    if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
    const response = await fetch(path, {
      method: "POST",
      body: form,
      credentials: "same-origin",
      headers,
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as {
        detail?: string;
        error?: string;
      } | null;
      throw new ApiError(
        response.status,
        payload?.detail ??
          payload?.error ??
          `Upload failed (${response.status})`,
      );
    }
    return response.json() as Promise<T>;
  },
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body, csrf: true }),
  async login(username: string, password: string) {
    const result = await request<LoginResult>("/api/auth/login", {
      method: "POST",
      body: { username, password },
    });
    csrfToken = result.csrf;
    return result;
  },
  async me() {
    const result = await request<SessionInfo>("/api/auth/me");
    csrfToken = result.csrf;
    return result;
  },
  async logout() {
    const result = await request<{ ok: boolean }>("/api/auth/logout", {
      method: "POST",
      csrf: true,
    });
    csrfToken = null;
    return result;
  },
};

export interface User {
  username: string;
  display_name: string | null;
  role: string;
}
export interface LoginResult {
  user: User;
  csrf: string;
}
export interface SessionInfo extends LoginResult {
  demo_mode: boolean;
  version: string;
}
export interface ScanSummary {
  id: string;
  name: string;
  status: string;
  profile: string;
  created_at: string | null;
  completed_at: string | null;
  overall_disposition: string | null;
  findings_count: number;
  critical_count: number;
  quarantine_count: number;
  review_count: number;
  coverage: { assessed: number; partial: number; total: number; pct: number };
  report_digest: string | null;
}
export interface Finding {
  id: string;
  title: string;
  reason: string;
  severity: string;
  confidence: number;
  attack_class: string;
  detector_id: string;
  layer: string;
  availability: string;
  recommended_disposition: string;
  evidence?: Array<{
    id: string;
    digest?: string;
    title: string;
    summary?: string;
    kind?: string;
    data?: Record<string, unknown> | null;
    blob?: { digest: string; media_type: string; size_bytes: number } | null;
  }>;
}
export interface PlanEntry {
  detector_id: string;
  detector_version?: string;
  availability: string;
  mode?: string;
  reason?: string;
  missing_required?: string[];
}
