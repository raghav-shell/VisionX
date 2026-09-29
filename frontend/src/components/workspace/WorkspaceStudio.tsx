"use client";

import {
  FormEvent,
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  Boxes,
  ChevronRight,
  Fingerprint,
  LoaderCircle,
  LogOut,
  Play,
  RefreshCw,
  ScanLine,
  ShieldCheck,
  Terminal,
  Users,
  Upload,
  Download,
  FileCheck2,
  X,
} from "lucide-react";
import {
  api,
  ApiError,
  Finding,
  PlanEntry,
  ScanSummary,
  SessionInfo,
} from "@/lib/api";

type Asset = {
  id: string;
  name: string;
  kind: string;
  digest: string;
  details?: Record<string, unknown>;
};
type Profile = { name: string; description: string; budget: string };
type Scenario = {
  scenario_id: string;
  attack_class: string;
  description?: string;
};
type CoverageRow = {
  attack_class: string;
  state: string;
  reason?: string;
  detectors?: string[];
};
type Contributor = {
  contributor_id?: string;
  contributor?: string;
  sample_count?: number;
  flagged_count?: number;
  posterior_anomaly?: number;
  [key: string]: unknown;
};
type ScanDetails = {
  findings: Finding[];
  plan: PlanEntry[];
  coverage: CoverageRow[];
  contributors: Contributor[];
  drift: Record<string, unknown>;
  provenance: Record<string, unknown>;
  graph: { nodes?: unknown[]; edges?: unknown[] };
};

const absentDetails: ScanDetails = {
  findings: [],
  plan: [],
  coverage: [],
  contributors: [],
  drift: {},
  provenance: {},
  graph: {},
};

function short(value: string | null | undefined, size = 14) {
  if (!value) return "—";
  return value.length <= size ? value : `${value.slice(0, size)}…`;
}

function tone(value: string | null | undefined) {
  const normalized = (value ?? "").toUpperCase();
  if (
    ["CRITICAL", "HIGH", "QUARANTINE", "FAILED", "ERROR"].some((item) =>
      normalized.includes(item),
    )
  )
    return "text-rose-300 border-rose-400/30 bg-rose-400/10";
  if (
    ["REVIEW", "MEDIUM", "DEGRADED", "PARTIALLY", "UNAVAILABLE"].some((item) =>
      normalized.includes(item),
    )
  )
    return "text-amber-200 border-amber-300/30 bg-amber-300/10";
  return "text-emerald-300 border-emerald-400/30 bg-emerald-400/10";
}

function Badge({ value }: { value: string | null | undefined }) {
  return (
    <span
      className={`inline-flex rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${tone(value)}`}
    >
      {value ?? "unknown"}
    </span>
  );
}

function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-white/15 bg-black/20 p-7 text-sm leading-6 text-white/50">
      {children}
    </div>
  );
}

function Login({ onReady }: { onReady: (session: SessionInfo) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = await api.login(username, password);
      onReady({ ...session, demo_mode: false, version: "" });
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to start a session",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[#070709] px-5 text-white">
      <form
        onSubmit={submit}
        className="w-full max-w-md rounded-2xl border border-white/10 bg-[#101014] p-7 shadow-2xl shadow-black/40"
      >
        <div className="mb-8 flex items-center gap-3">
          <ShieldCheck className="h-8 w-8 text-cyan-300" />
          <div>
            <h1 className="font-display text-2xl font-semibold">
              VisionSentinel
            </h1>
            <p className="text-sm text-white/50">
              Air-gapped assurance workspace
            </p>
          </div>
        </div>
        <label className="mb-4 block text-sm text-white/70">
          Username
          <input
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-white/15 bg-black/40 px-3 py-2.5 text-white outline-none focus:border-cyan-300"
            autoComplete="username"
          />
        </label>
        <label className="mb-5 block text-sm text-white/70">
          Password
          <input
            required
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-white/15 bg-black/40 px-3 py-2.5 text-white outline-none focus:border-cyan-300"
            autoComplete="current-password"
          />
        </label>
        {error && (
          <p className="mb-4 rounded-lg border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-200">
            {error}
          </p>
        )}
        <button
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-200 px-4 py-2.5 text-sm font-semibold text-black disabled:opacity-60"
        >
          {busy && <LoaderCircle className="h-4 w-4 animate-spin" />}Sign in
          locally
        </button>
        <p className="mt-5 text-xs leading-5 text-white/40">
          This interface only communicates with the same-origin VisionSentinel
          API. Accounts are managed by your local operator.
        </p>
      </form>
    </main>
  );
}

function NewScan({
  assets,
  profiles,
  onSubmitted,
}: {
  assets: Asset[];
  profiles: Profile[];
  onSubmitted: (scan: ScanSummary) => void;
}) {
  const [name, setName] = useState("New assurance scan");
  const [profile, setProfile] = useState("");
  const [dataset, setDataset] = useState("");
  const [model, setModel] = useState("");
  const [ledger, setLedger] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const candidates = (kind: string) =>
    assets.filter((asset) => asset.kind === kind);

  useEffect(() => {
    if (!profile && profiles[0]) setProfile(profiles[0].name);
  }, [profile, profiles]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<{ scan_id: string }>("/api/scans", {
        name,
        profile,
        ...(dataset && { dataset }),
        ...(model && { model }),
        ...(ledger && { ledger }),
      });
      const scan = await api.get<ScanSummary>(
        `/api/scans/${encodeURIComponent(result.scan_id)}`,
      );
      onSubmitted(scan);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Scan could not be submitted",
      );
    } finally {
      setBusy(false);
    }
  }
  const select = (
    label: string,
    value: string,
    setValue: (value: string) => void,
    kind: string,
  ) => (
    <label className="block text-xs font-medium uppercase tracking-wide text-white/50">
      {label}
      <select
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="mt-2 w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2.5 text-sm text-white"
      >
        <option value="">Not supplied</option>
        {candidates(kind).map((asset) => (
          <option key={asset.id} value={asset.id}>
            {asset.name} · {short(asset.digest, 10)}
          </option>
        ))}
      </select>
    </label>
  );
  return (
    <form
      onSubmit={submit}
      className="grid gap-4 rounded-xl border border-cyan-300/20 bg-cyan-300/[0.04] p-5 md:grid-cols-2"
    >
      <div className="md:col-span-2 flex items-center gap-2 text-sm font-semibold">
        <ScanLine className="h-4 w-4 text-cyan-300" />
        New assessment
      </div>
      <label className="block text-xs font-medium uppercase tracking-wide text-white/50">
        Name
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={120}
          className="mt-2 w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2.5 text-sm text-white"
        />
      </label>
      <label className="block text-xs font-medium uppercase tracking-wide text-white/50">
        Profile
        <select
          value={profile}
          onChange={(e) => setProfile(e.target.value)}
          className="mt-2 w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2.5 text-sm text-white"
        >
          {profiles.map((item) => (
            <option key={item.name} value={item.name}>
              {item.name} · {item.budget}
            </option>
          ))}
        </select>
      </label>
      {select("Dataset asset", dataset, setDataset, "dataset")}
      {select("Model asset", model, setModel, "model")}
      {select("Inference ledger", ledger, setLedger, "ledger")}
      <div className="flex items-end">
        <button
          disabled={busy || (!dataset && !model && !ledger)}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-black disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          {busy ? "Submitting…" : "Plan and run scan"}
        </button>
      </div>
      {error && <p className="md:col-span-2 text-sm text-rose-200">{error}</p>}
      <p className="md:col-span-2 text-xs text-white/45">
        Only imported asset identifiers are sent to the API; the browser never
        supplies server file paths.
      </p>
    </form>
  );
}

function AssetIntake({ onUploaded }: { onUploaded: (asset: Asset) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState("dataset");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("kind", kind);
      onUploaded(await api.upload<Asset>("/api/assets/upload", form));
      setFile(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form
      onSubmit={submit}
      className="flex flex-wrap items-end gap-3 rounded-xl border border-white/10 bg-white/[0.025] p-4"
    >
      <div>
        <p className="font-mono text-[10px] uppercase text-white/45">
          Asset intake
        </p>
        <p className="mt-1 text-xs text-white/55">
          Upload enters the controlled workspace before scanning.
        </p>
      </div>
      <label className="ml-auto text-xs text-white/55">
        Kind
        <select
          value={kind}
          onChange={(event) => setKind(event.target.value)}
          className="ml-2 rounded border border-white/10 bg-black/40 px-2 py-1.5 text-white"
        >
          <option>dataset</option>
          <option>model</option>
          <option>ledger</option>
          <option>preprocess</option>
          <option>anchor</option>
          <option>trust_root</option>
          <option>inputs</option>
          <option>fingerprint</option>
        </select>
      </label>
      <input
        type="file"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        className="max-w-56 text-xs text-white/60 file:mr-2 file:rounded file:border-0 file:bg-white/10 file:px-2 file:py-1.5 file:text-white"
      />
      <button
        disabled={!file || busy}
        className="flex items-center gap-2 rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-3 py-2 text-xs text-cyan-100 disabled:opacity-40"
      >
        <Upload className="h-3.5 w-3.5" />
        {busy ? "Uploading…" : "Import asset"}
      </button>
      {error && <p className="w-full text-xs text-rose-200">{error}</p>}
    </form>
  );
}

function DetailPane({
  tab,
  details,
  scan,
}: {
  tab: string;
  details: ScanDetails;
  scan: ScanSummary;
}) {
  const [selectedEvidence, setSelectedEvidence] = useState<{
    title: string;
    summary?: string;
    kind?: string;
    data?: Record<string, unknown> | null;
    blob?: { digest: string; media_type: string; size_bytes: number } | null;
  } | null>(null);
  function AssetUploader({
    onUploaded,
  }: {
    onUploaded: (asset: Asset) => void;
  }) {
    const [file, setFile] = useState<File | null>(null);
    const [kind, setKind] = useState("dataset");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    async function submit(event: FormEvent) {
      event.preventDefault();
      if (!file) return;
      setBusy(true);
      setError(null);
      try {
        const form = new FormData();
        form.append("file", file);
        form.append("kind", kind);
        onUploaded(await api.upload<Asset>("/api/assets/upload", form));
        setFile(null);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Upload failed");
      } finally {
        setBusy(false);
      }
    }
    return (
      <form
        onSubmit={submit}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-white/10 bg-white/[0.025] p-4"
      >
        <div>
          <p className="font-mono text-[10px] uppercase text-white/45">
            Asset intake
          </p>
          <p className="mt-1 text-xs text-white/55">
            Upload enters the controlled workspace before scanning.
          </p>
        </div>
        <label className="ml-auto text-xs text-white/55">
          Kind
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="ml-2 rounded border border-white/10 bg-black/40 px-2 py-1.5 text-white"
          >
            <option>dataset</option>
            <option>model</option>
            <option>ledger</option>
            <option>preprocess</option>
            <option>anchor</option>
            <option>trust_root</option>
            <option>inputs</option>
            <option>fingerprint</option>
          </select>
        </label>
        <input
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="max-w-56 text-xs text-white/60 file:mr-2 file:rounded file:border-0 file:bg-white/10 file:px-2 file:py-1.5 file:text-white"
        />
        <button
          disabled={!file || busy}
          className="flex items-center gap-2 rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-3 py-2 text-xs text-cyan-100 disabled:opacity-40"
        >
          <Upload className="h-3.5 w-3.5" />
          {busy ? "Uploading…" : "Import asset"}
        </button>
        {error && <p className="w-full text-xs text-rose-200">{error}</p>}
      </form>
    );
  }
  if (tab === "findings")
    return (
      <section className="space-y-3">
        {details.findings.length ? (
          details.findings.map((finding) => (
            <article
              key={finding.id}
              className="rounded-xl border border-white/10 bg-white/[0.025] p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-mono text-xs text-cyan-200">
                    {finding.detector_id} · {finding.attack_class}
                  </p>
                  <h3 className="mt-1 text-base font-semibold">
                    {finding.title}
                  </h3>
                </div>
                <div className="flex gap-2">
                  <Badge value={finding.severity} />
                  <Badge value={finding.recommended_disposition} />
                </div>
              </div>
              <p className="mt-3 text-sm leading-6 text-white/65">
                {finding.reason}
              </p>
              <div className="mt-4 flex flex-wrap gap-4 font-mono text-[11px] text-white/45">
                <span>confidence {Math.round(finding.confidence * 100)}%</span>
                <span>availability {finding.availability}</span>
                <span>evidence {finding.evidence?.length ?? 0}</span>
              </div>
              {!!finding.evidence?.length && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {finding.evidence.map((evidence) => (
                    <button key={evidence.id} onClick={() => setSelectedEvidence(evidence)}
                      className="rounded border border-cyan-300/25 bg-cyan-300/5 px-2 py-1 font-mono text-[11px] text-cyan-100 hover:bg-cyan-300/15">
                      Inspect: {evidence.title}
                    </button>
                  ))}
                </div>
              )}
            </article>
          ))
        ) : (
          <EmptyState>
            This scan has no findings available yet. A running scan will
            populate this view when it is sealed.
          </EmptyState>
        )}
        {selectedEvidence && (
          <aside className="rounded-xl border border-cyan-300/30 bg-[#0b1519] p-5 shadow-xl" aria-label="Evidence detail">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-mono text-[10px] uppercase text-cyan-200">{selectedEvidence.kind ?? "evidence"}</p>
                <h3 className="mt-1 font-semibold">{selectedEvidence.title}</h3>
                {selectedEvidence.summary && <p className="mt-2 text-sm text-white/65">{selectedEvidence.summary}</p>}
              </div>
              <button onClick={() => setSelectedEvidence(null)} className="rounded p-1 text-white/60 hover:bg-white/10" aria-label="Close evidence detail"><X className="h-4 w-4" /></button>
            </div>
            {selectedEvidence.data && <pre className="mt-4 max-h-64 overflow-auto rounded bg-black/35 p-3 text-xs text-cyan-100/80">{JSON.stringify(selectedEvidence.data, null, 2)}</pre>}
            {selectedEvidence.blob && <a href={`/api/evidence/${encodeURIComponent(selectedEvidence.blob.digest)}/raw`} target="_blank" rel="noreferrer"
              className="mt-4 inline-flex items-center gap-2 rounded border border-cyan-300/30 px-3 py-2 text-xs text-cyan-100"><Download className="h-3.5 w-3.5" />Download verified raw evidence ({selectedEvidence.blob.size_bytes} bytes)</a>}
          </aside>
        )}
      </section>
    );
  if (tab === "coverage")
    return (
      <section className="rounded-xl border border-white/10 bg-white/[0.025] p-5">
        <h2 className="mb-4 font-semibold">Assessment coverage</h2>
        {details.coverage.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-white/10 font-mono text-[11px] uppercase text-white/40">
                <tr>
                  <th className="pb-3">Attack class</th>
                  <th className="pb-3">State</th>
                  <th className="pb-3">Reason</th>
                </tr>
              </thead>
              <tbody>
                {details.coverage.map((row) => (
                  <tr
                    key={row.attack_class}
                    className="border-b border-white/5"
                  >
                    <td className="py-3 font-mono text-white/80">
                      {row.attack_class}
                    </td>
                    <td className="py-3">
                      <Badge value={row.state} />
                    </td>
                    <td className="py-3 text-white/55">{row.reason ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState>
            Coverage is calculated from the stored scan plan once execution
            completes.
          </EmptyState>
        )}
      </section>
    );
  if (tab === "contributors")
    return (
      <section className="rounded-xl border border-white/10 bg-white/[0.025] p-5">
        <h2 className="mb-4 font-semibold">Contributor assessment</h2>
        {details.contributors.length ? (
          <div className="space-y-2">
            {details.contributors.map((row, index) => (
              <div
                key={`${row.contributor_id ?? row.contributor ?? "contributor"}-${index}`}
                className="grid gap-2 rounded-lg border border-white/8 bg-black/20 p-4 text-sm md:grid-cols-5"
              >
                <span className="font-mono text-cyan-200">
                  {String(row.contributor_id ?? row.contributor ?? "unknown")}
                </span>
                <span>{String(row.sample_count ?? "—")} samples</span>
                <span>{String(row.flagged_count ?? "—")} flagged</span>
                <span>
                  posterior{" "}
                  {typeof row.posterior_anomaly === "number"
                    ? `${Math.round(row.posterior_anomaly * 100)}%`
                    : "—"}
                </span>
                <span className="text-white/55">CI {confidenceInterval(row)}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState>
            No contributor-risk result was produced for the supplied assets.
          </EmptyState>
        )}
      </section>
    );
  if (tab === "drift")
    return (
      <DataPanel
        title="Drift assessment"
        value={details.drift}
        empty="No drift comparison was requested or the scan is still running."
      />
    );
  if (tab === "provenance")
    return (
      <DataPanel
        title="Provenance verification"
        value={details.provenance}
        empty="No inference ledger was included in this scan."
      />
    );
  if (tab === "graph")
    return (
      <section className="rounded-xl border border-white/10 bg-white/[0.025] p-5">
        <h2 className="mb-2 font-semibold">Evidence graph</h2>
        <p className="mb-4 text-sm text-white/55">
          Nodes and edges are generated by the completed scan; graph content is
          never inferred by the UI.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <Metric
            label="Nodes"
            value={String(details.graph.nodes?.length ?? 0)}
          />
          <Metric
            label="Edges"
            value={String(details.graph.edges?.length ?? 0)}
          />
        </div>
      </section>
    );
  return (
    <section className="rounded-xl border border-white/10 bg-white/[0.025] p-5">
      <h2 className="mb-4 font-semibold">Capability plan</h2>
      {details.plan.length ? (
        <div className="space-y-2">
          {details.plan.map((item) => (
            <div
              key={item.detector_id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/8 bg-black/20 px-4 py-3"
            >
              <div>
                <p className="font-mono text-sm text-white/85">
                  {item.detector_id}
                </p>
                <p className="mt-1 text-xs text-white/45">
                  {item.reason ?? item.mode ?? "No additional plan note"}
                </p>
              </div>
              <Badge value={item.availability} />
            </div>
          ))}
        </div>
      ) : (
        <EmptyState>
          The persisted plan will appear after the engine probes the supplied
          assets.
        </EmptyState>
      )}
    </section>
  );
}

function DataPanel({
  title,
  value,
  empty,
}: {
  title: string;
  value: Record<string, unknown>;
  empty: string;
}) {
  return (
    <section className="rounded-xl border border-white/10 bg-white/[0.025] p-5">
      <h2 className="mb-4 font-semibold">{title}</h2>
      {Object.keys(value).length ? (
        <pre className="max-h-[560px] overflow-auto rounded-lg border border-white/8 bg-black/40 p-4 font-mono text-xs leading-6 text-cyan-100/80">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : (
        <EmptyState>{empty}</EmptyState>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/30 p-4">
      <p className="font-mono text-[10px] uppercase tracking-wide text-white/45">
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}

function confidenceInterval(row: Contributor) {
  const interval = row.confidence_interval ?? row.credible_interval ?? row.ci;
  if (Array.isArray(interval) && interval.length === 2) return `${Number(interval[0]).toFixed(2)}–${Number(interval[1]).toFixed(2)}`;
  const low = row.ci_lower ?? row.lower_ci;
  const high = row.ci_upper ?? row.upper_ci;
  return typeof low === "number" && typeof high === "number" ? `${low.toFixed(2)}–${high.toFixed(2)}` : "not reported";
}

export default function WorkspaceStudio() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [scans, setScans] = useState<ScanSummary[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [system, setSystem] = useState<Record<string, unknown>>({});
  const [selectedScan, setSelectedScan] = useState<string | null>(null);
  const [details, setDetails] = useState<ScanDetails>(absentDetails);
  const [tab, setTab] = useState("plan");
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [scenarioId, setScenarioId] = useState("");
  const [runningScenario, setRunningScenario] = useState(false);
  const [reportVerification, setReportVerification] = useState<string | null>(null);

  useEffect(() => {
    api
      .me()
      .then(setSession)
      .catch(() => null)
      .finally(() => setCheckingSession(false));
  }, []);
  const loadWorkspace = useCallback(async () => {
    if (!session) return;
    setRefreshing(true);
    setError(null);
    try {
      const [
        scanResponse,
        assetResponse,
        profileResponse,
        scenarioResponse,
        statusResponse,
      ] = await Promise.all([
        api.get<{ scans: ScanSummary[] }>("/api/scans"),
        api.get<{ assets: Asset[] }>("/api/assets"),
        api.get<{ profiles: Profile[] }>("/api/system/profiles"),
        api.get<{ scenarios: Scenario[] }>("/api/attacklab/scenarios"),
        api.get<Record<string, unknown>>("/api/system/status"),
      ]);
      setScans(scanResponse.scans);
      setAssets(assetResponse.assets);
      setProfiles(profileResponse.profiles);
      setScenarios(scenarioResponse.scenarios);
      setSystem(statusResponse);
      setSelectedScan((current) =>
        current && scanResponse.scans.some((scan) => scan.id === current)
          ? current
          : (scanResponse.scans[0]?.id ?? null),
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to load workspace data",
      );
    } finally {
      setRefreshing(false);
    }
  }, [session]);
  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);
  const loadDetails = useCallback(async () => {
    if (!selectedScan) {
      setDetails(absentDetails);
      return;
    }
    try {
      const root = `/api/scans/${encodeURIComponent(selectedScan)}`;
      const [findings, plan, coverage, contributors, drift, provenance, graph] =
        await Promise.all([
          api.get<{ findings: Finding[] }>(`${root}/findings`),
          api.get<{ plan: PlanEntry[] }>(`${root}/plan`),
          api.get<CoverageRow[] | { rows?: CoverageRow[] }>(`${root}/coverage`),
          api.get<Contributor[] | { contributors?: Contributor[] }>(
            `${root}/contributors`,
          ),
          api.get<Record<string, unknown>>(`${root}/drift`),
          api.get<Record<string, unknown>>(`${root}/provenance`),
          api.get<{ nodes?: unknown[]; edges?: unknown[] }>(`${root}/graph`),
        ]);
      setDetails({
        findings: findings.findings,
        plan: plan.plan,
        coverage: Array.isArray(coverage) ? coverage : (coverage.rows ?? []),
        contributors: Array.isArray(contributors)
          ? contributors
          : (contributors.contributors ?? []),
        drift,
        provenance,
        graph,
      });
    } catch (cause) {
      if (!(cause instanceof ApiError && cause.status === 404))
        setError(
          cause instanceof Error
            ? cause.message
            : "Unable to load scan details",
        );
      setDetails(absentDetails);
    }
  }, [selectedScan]);
  useEffect(() => {
    void loadDetails();
  }, [loadDetails]);
  useEffect(() => {
    const timer = window.setInterval(() => void loadWorkspace(), 5000);
    return () => window.clearInterval(timer);
  }, [loadWorkspace]);

  const current = useMemo(
    () => scans.find((scan) => scan.id === selectedScan) ?? null,
    [scans, selectedScan],
  );
  async function runScenario() {
    if (!scenarioId) return;
    setRunningScenario(true);
    setError(null);
    try {
      const result = await api.post<{ scan_id: string }>(
        `/api/attacklab/scenarios/${encodeURIComponent(scenarioId)}/run`,
        {
          profile:
            profiles.find((profile) => profile.name === "selftest")?.name ??
            profiles[0]?.name ??
            "baseline",
        },
      );
      await loadWorkspace();
      setSelectedScan(result.scan_id);
      setTab("findings");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Scenario failed");
    } finally {
      setRunningScenario(false);
    }
  }
  async function logout() {
    await api.logout().catch(() => null);
    setSession(null);
    setScans([]);
    setSelectedScan(null);
  }
  async function verifyReport() {
    if (!current) return;
    setReportVerification(null);
    try {
      const result = await api.post<{ verified: boolean; problems: string[] }>(`/api/scans/${encodeURIComponent(current.id)}/report/verify`, { expected_digest: current.report_digest });
      setReportVerification(result.verified ? "Signed manifest and report digest verified." : `Verification failed: ${result.problems.join("; ") || "digest mismatch"}`);
    } catch (cause) {
      setReportVerification(cause instanceof Error ? cause.message : "Unable to verify report");
    }
  }
  if (checkingSession)
    return (
      <main className="grid min-h-screen place-items-center bg-[#070709] text-white">
        <LoaderCircle className="h-6 w-6 animate-spin text-cyan-300" />
      </main>
    );
  if (!session) return <Login onReady={setSession} />;
  const nav = [
    ["plan", Terminal, "Plan"],
    ["findings", AlertTriangle, "Findings"],
    ["coverage", ShieldCheck, "Coverage"],
    ["contributors", Users, "Contributors"],
    ["drift", Activity, "Drift"],
    ["provenance", Fingerprint, "Provenance"],
    ["graph", Boxes, "Evidence graph"],
  ] as const;
  const mayOperate = ["ANALYST", "APPROVER", "ADMIN"].includes(
    session.user.role,
  );
  return (
    <div className="min-h-screen bg-[#070709] text-white">
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-white/10 bg-[#0c0c10]/95 px-4 backdrop-blur">
        <Link
          href="/"
          className="flex items-center gap-2 font-display font-semibold"
        >
          <ShieldCheck className="h-5 w-5 text-cyan-300" />
          VisionSentinel{" "}
          <span className="font-mono text-[10px] text-cyan-200">WORKSPACE</span>
        </Link>
        <div className="flex items-center gap-3">
          <span className="hidden font-mono text-[10px] text-emerald-300 sm:inline">
            AIR-GAPPED · SAME-ORIGIN
          </span>
          <span className="text-xs text-white/60">
            {session.user.display_name ?? session.user.username} ·{" "}
            {session.user.role}
          </span>
          <button
            onClick={() => void logout()}
            className="rounded p-2 text-white/60 hover:bg-white/10 hover:text-white"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>
      <div className="mx-auto grid max-w-[1600px] gap-5 p-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <div className="rounded-xl border border-white/10 bg-white/[0.025] p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase text-white/45">
                Scans
              </span>
              <button
                onClick={() => void loadWorkspace()}
                className="p-1 text-cyan-200 disabled:opacity-40"
                disabled={refreshing}
              >
                <RefreshCw
                  className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
                />
              </button>
            </div>
            <div className="max-h-72 space-y-1 overflow-auto">
              {scans.map((scan) => (
                <button
                  key={scan.id}
                  onClick={() => setSelectedScan(scan.id)}
                  className={`w-full rounded-lg border p-3 text-left ${scan.id === selectedScan ? "border-cyan-300/50 bg-cyan-300/10" : "border-transparent hover:bg-white/5"}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-xs">
                      {scan.name}
                    </span>
                    <Badge value={scan.overall_disposition ?? scan.status} />
                  </div>
                  <p className="mt-1 text-[11px] text-white/45">
                    {scan.findings_count} findings · {scan.coverage.pct}%
                    coverage
                  </p>
                </button>
              ))}
              {!scans.length && (
                <p className="p-2 text-sm text-white/45">No scans recorded.</p>
              )}
            </div>
          </div>
          <nav className="rounded-xl border border-white/10 bg-white/[0.025] p-2">
            {nav.map(([id, Icon, label]) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm ${tab === id ? "bg-white/10 text-white" : "text-white/55 hover:bg-white/5 hover:text-white"}`}
              >
                <Icon className="h-4 w-4 text-cyan-200" />
                {label}
                <ChevronRight className="ml-auto h-3.5 w-3.5 opacity-50" />
              </button>
            ))}
          </nav>
          <div className="rounded-xl border border-white/10 bg-white/[0.025] p-4">
            <p className="font-mono text-[10px] uppercase text-white/45">
              Engine
            </p>
            <p className="mt-2 text-sm text-white/75">
              {String(
                (system.engine as { detectors?: number } | undefined)
                  ?.detectors ?? "—",
              )}{" "}
              registered detectors
            </p>
            <p className="mt-1 text-xs text-white/45">
              {String(
                (system.network as { outbound?: string } | undefined)
                  ?.outbound ?? "status unavailable",
              )}
            </p>
          </div>
        </aside>
        <main className="min-w-0 space-y-5">
          <section className="rounded-xl border border-white/10 bg-gradient-to-br from-[#11131a] to-[#09090c] p-6">
            <div className="flex flex-col justify-between gap-5 md:flex-row md:items-start">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-200">
                  Mission control
                </p>
                <h1 className="mt-2 text-2xl font-semibold">
                  {current?.name ?? "No selected scan"}
                </h1>
                <p className="mt-2 max-w-2xl text-sm text-white/55">
                  Assessment coverage is a measure of which attack classes were
                  evaluated, not a security score. Every displayed result comes
                  from the sealed scan result.
                </p>
              </div>
              {current && (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <Metric
                    label="Findings"
                    value={String(current.findings_count)}
                  />
                  <Metric
                    label="Critical"
                    value={String(current.critical_count)}
                  />
                  {mayOperate && (
                    <AssetIntake
                      onUploaded={(asset) =>
                        setAssets((previous) => [asset, ...previous])
                      }
                    />
                  )}

                  <Metric label="Review" value={String(current.review_count)} />
                  <Metric label="Coverage" value={`${current.coverage.pct}%`} />
                </div>
              )}
            </div>
            {current && (
              <div className="mt-5 flex flex-wrap gap-2 text-xs text-white/45">
                <span className="rounded bg-white/5 px-2 py-1 font-mono">
                  {current.id}
                </span>
                <span className="rounded bg-white/5 px-2 py-1">
                  profile {current.profile}
                </span>
                <span className="rounded bg-white/5 px-2 py-1">
                  report {short(current.report_digest)}
                </span>
                <a href={`/api/scans/${encodeURIComponent(current.id)}/bundle/manifest.json`} className="inline-flex items-center gap-1 rounded bg-white/5 px-2 py-1 text-cyan-100"><Download className="h-3 w-3" />manifest</a>
                <a href={`/api/scans/${encodeURIComponent(current.id)}/bundle/coverage.md`} className="inline-flex items-center gap-1 rounded bg-white/5 px-2 py-1 text-cyan-100"><Download className="h-3 w-3" />coverage</a>
                <button onClick={() => void verifyReport()} className="inline-flex items-center gap-1 rounded border border-emerald-300/25 px-2 py-1 text-emerald-200"><FileCheck2 className="h-3 w-3" />verify signed report</button>
              </div>
            )}
            {reportVerification && <p className="mt-3 text-xs text-white/65" role="status">{reportVerification}</p>}
          </section>
          {error && (
            <div className="rounded-xl border border-rose-400/30 bg-rose-400/10 p-4 text-sm text-rose-100">
              {error}
            </div>
          )}
          {mayOperate && (
            <NewScan
              assets={assets}
              profiles={profiles}
              onSubmitted={(scan) => {
                setScans((previous) => [scan, ...previous]);
                setSelectedScan(scan.id);
              }}
            />
          )}
          <section className="rounded-xl border border-white/10 bg-white/[0.025] p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] uppercase text-white/45">
                  Controlled attack lab
                </p>
                <p className="mt-1 text-sm text-white/65">
                  Run only shipped, reproducible scenarios; the UI cannot
                  execute arbitrary commands.
                </p>
              </div>
              {mayOperate && (
                <div className="flex gap-2">
                  <select
                    value={scenarioId}
                    onChange={(e) => setScenarioId(e.target.value)}
                    className="max-w-60 rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm"
                  >
                    <option value="">Select scenario</option>
                    {scenarios.map((scenario) => (
                      <option
                        key={scenario.scenario_id}
                        value={scenario.scenario_id}
                      >
                        {scenario.scenario_id} · {scenario.attack_class}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => void runScenario()}
                    disabled={!scenarioId || runningScenario}
                    className="flex items-center gap-2 rounded-lg border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-sm text-amber-100 disabled:opacity-40"
                  >
                    <Play className="h-4 w-4" />
                    {runningScenario ? "Running…" : "Run"}
                  </button>
                </div>
              )}
            </div>
          </section>
          <DetailPane
            tab={tab}
            details={details}
            scan={
              current ??
              ({
                id: "",
                name: "",
                status: "",
                profile: "",
                created_at: null,
                completed_at: null,
                overall_disposition: null,
                findings_count: 0,
                critical_count: 0,
                quarantine_count: 0,
                review_count: 0,
                coverage: { assessed: 0, partial: 0, total: 0, pct: 0 },
                report_digest: null,
              } satisfies ScanSummary)
            }
          />
        </main>
      </div>
    </div>
  );
}
