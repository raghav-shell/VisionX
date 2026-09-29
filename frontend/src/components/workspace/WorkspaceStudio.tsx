"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, ReactNode } from "react";
import Link from "next/link";
import {
  Activity, ArrowLeft, ArrowRight, Check, CheckCircle2,
  ChevronDown, ChevronRight, CircleAlert, CircleDashed, Clipboard, Clock3,
  Database, FileJson2, FileSearch2, FileText, Fingerprint, FolderOpen,
  GitBranch, Layers3, LockKeyhole, Menu, PanelRightClose, PanelRightOpen,
  Moon, Plus, Search, Shield, ShieldAlert, SlidersHorizontal, Sun, Terminal, X,
} from "lucide-react";
import VisionXLogo from "../VisionXLogo";
import { emptyWorkspaceScan, parseReport } from "./workspace-data";
import type { CoverageRecord, CoverageState, Disposition, FindingRecord, WorkspaceScan } from "./workspace-data";
import { currentSession, discoverApi, loadServerAssets, loadServerProfiles, loadServerScans, login, logout, submitServerScan } from "./workspace-api";
import type { ApiAsset, ApiProfile, ApiSession } from "./workspace-api";
import "./workspace.css";

type View = "overview" | "findings" | "coverage" | "detectors" | "evidence" | "assets" | "provenance" | "activity";
type Inspector = { kind: "scan" } | { kind: "finding"; id: string } | { kind: "coverage"; id: string } | { kind: "execution"; id: string } | { kind: "asset"; id: string };

const navigation: { id: View; label: string; icon: typeof Layers3 }[] = [
  { id: "overview", label: "Overview", icon: Layers3 },
  { id: "findings", label: "Findings", icon: ShieldAlert },
  { id: "coverage", label: "Coverage", icon: CircleDashed },
  { id: "detectors", label: "Detectors", icon: Activity },
  { id: "evidence", label: "Evidence", icon: FileSearch2 },
  { id: "assets", label: "Assets", icon: Database },
  { id: "provenance", label: "Provenance", icon: GitBranch },
  { id: "activity", label: "Activity", icon: Clock3 },
];

const tone: Record<string, string> = {
  QUARANTINE: "rose", REVIEW: "amber", ACCEPT: "mint", HIGH: "rose", CRITICAL: "rose", MEDIUM: "amber", LOW: "blue",
  ASSESSED: "mint", PARTIALLY_ASSESSED: "amber", NOT_ASSESSED: "muted", FAILED_TO_EXECUTE: "rose", UNSUPPORTED: "muted",
  COMPLETED: "mint", COMPLETED_DEGRADED: "amber", ABSTAINED: "muted", NOT_RUN: "muted", ERROR: "rose", READY: "mint", DEGRADED: "amber", UNAVAILABLE: "muted",
};

function label(value: string) { return value.replaceAll("_", " ").toLowerCase(); }
function date(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
function short(value?: string | null, length = 16) { return value ? `${value.slice(0, length)}…` : "—"; }
function disposition(scan: WorkspaceScan): Disposition | null { return scan.summary?.overall_disposition ?? null; }
function Badge({ value, children }: { value: string; children?: ReactNode }) {
  return <span className={`vx-badge vx-badge--${tone[value] ?? "muted"}`}>{children ?? label(value)}</span>;
}
function Empty({ title, text, icon: Icon = FileSearch2 }: { title: string; text: string; icon?: typeof FileSearch2 }) {
  return <div className="vx-empty"><div className="vx-empty-icon"><Icon size={20} /></div><h3>{title}</h3><p>{text}</p></div>;
}
function SectionTitle({ eyebrow, title, action }: { eyebrow?: string; title: string; action?: ReactNode }) {
  return <div className="vx-section-title"><div><span>{eyebrow}</span><h2>{title}</h2></div>{action}</div>;
}
function RowArrow() { return <ChevronRight className="vx-row-arrow" size={16} aria-hidden="true" />; }

export default function WorkspaceStudio() {
  const [imported, setImported] = useState<WorkspaceScan[]>([]);
  const [serverScans, setServerScans] = useState<WorkspaceScan[]>([]);
  const [serverProfiles, setServerProfiles] = useState<ApiProfile[]>([]);
  const [apiState, setApiState] = useState<"checking" | "unavailable" | "signed-out" | "connected">("checking");
  const [session, setSession] = useState<ApiSession | null>(null);
  const [loginOpen, setLoginOpen] = useState(false);
  const scans = useMemo(() => [...serverScans, ...imported], [serverScans, imported]);
  const [selectedId, setSelectedId] = useState("");
  const [view, setView] = useState<View>("overview");
  const [inspector, setInspector] = useState<Inspector | null>({ kind: "scan" });
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [inspectorOverlay, setInspectorOverlay] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [newScanOpen, setNewScanOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [findingFilter, setFindingFilter] = useState("ALL");
  const [coverageFilter, setCoverageFilter] = useState("ALL");
  const [notice, setNotice] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const fileRef = useRef<HTMLInputElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);
  const scan = scans.find(item => item.scan_id === selectedId) ?? scans[0] ?? emptyWorkspaceScan;

  useEffect(() => {
    const saved = window.localStorage.getItem("visionx.workspace.theme");
    if (saved === "dark") setTheme("dark");
  }, []);
  const toggleTheme = () => setTheme(current => {
    const next = current === "light" ? "dark" : "light";
    window.localStorage.setItem("visionx.workspace.theme", next);
    return next;
  });

  const refreshServer = useCallback(async () => {
    const next = await loadServerScans();
    setServerScans(next);
    return next;
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (!await discoverApi()) { if (!cancelled) setApiState("unavailable"); return; }
      try {
        const active = await currentSession();
        if (cancelled) return;
        if (!active) { setApiState("signed-out"); return; }
        setSession(active);
        setApiState("connected");
        const next = await refreshServer();
        void loadServerProfiles().then(setServerProfiles).catch(() => setServerProfiles([]));
        if (!cancelled && next.length) setSelectedId(next[0].scan_id);
      } catch { if (!cancelled) setApiState("signed-out"); }
    })();
    return () => { cancelled = true; };
  }, [refreshServer]);

  useEffect(() => {
    if (apiState !== "connected") return;
    const interval = window.setInterval(() => { void refreshServer().catch(() => {}); }, 10000);
    return () => window.clearInterval(interval);
  }, [apiState, refreshServer]);

  const signIn = async (username: string, password: string) => {
    const active = await login(username, password);
    setSession(active);
    setApiState("connected");
    setLoginOpen(false);
    const next = await refreshServer();
    void loadServerProfiles().then(setServerProfiles).catch(() => setServerProfiles([]));
    if (next.length) selectScan(next[0].scan_id);
    setNotice(`Connected as ${active.user.display_name || active.user.username}.`);
  };
  const signOut = async () => {
    if (!session) return;
    try { await logout(session.csrf); setSession(null); setServerScans([]); setApiState("signed-out"); selectScan(""); setNotice("Signed out of the local server."); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Could not sign out."); }
  };
  const queueServerScan = async (body: { name: string; profile: string; dataset?: string; model?: string }) => {
    if (!session) throw new Error("Sign in to the local server first.");
    const id = await submitServerScan(body, session.csrf);
    setNewScanOpen(false);
    const next = await refreshServer();
    if (next.some(item => item.scan_id === id)) selectScan(id);
    setNotice(`Assessment ${id} queued on the local server.`);
  };

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setPaletteOpen(current => !current); }
      if (event.key === "Escape") { setPaletteOpen(false); setNewScanOpen(false); setMobileOpen(false); }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  useEffect(() => { mainRef.current?.scrollTo({ top: 0, behavior: "instant" }); }, [view, selectedId]);
  useEffect(() => { if (!notice) return; const timeout = window.setTimeout(() => setNotice(""), 4000); return () => window.clearTimeout(timeout); }, [notice]);

  const selectScan = (id: string) => { setSelectedId(id); setView("overview"); setInspector({ kind: "scan" }); setFindingFilter("ALL"); setCoverageFilter("ALL"); setMobileOpen(false); setPaletteOpen(false); setInspectorOverlay(false); };
  const selectView = (next: View) => { setView(next); setMobileOpen(false); setPaletteOpen(false); setInspectorOverlay(false); if (next === "overview") setInspector({ kind: "scan" }); };
  const openInspector = (target: Inspector) => { setInspector(target); setInspectorOpen(true); setInspectorOverlay(true); };
  const copy = async (value: string, message = "Copied to clipboard") => { try { await navigator.clipboard.writeText(value); setNotice(message); } catch { setNotice("Clipboard unavailable in this browser."); } };
  const importFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) { setNotice("Report is too large. Maximum size is 15 MB."); return; }
    try {
      const result = parseReport(await file.text());
      setImported(current => [result, ...current.filter(item => item.scan_id !== result.scan_id)]);
      selectScan(result.scan_id);
      setNotice(`Opened ${result.name} locally. No file was uploaded.`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Could not read report.json."); }
  };

  const filteredFindings = scan.findings.filter(finding => findingFilter === "ALL" || finding.recommended_disposition === findingFilter);
  const filteredCoverage = scan.coverage.rows.filter(row => coverageFilter === "ALL" || row.state === coverageFilter);
  const evidence = scan.findings.flatMap(finding => finding.evidence.map(item => ({ ...item, finding })));
  const attentionCount = scan.findings.filter(item => item.recommended_disposition !== "ACCEPT").length;
  const coveragePercent = scan.coverage.total ? Math.round(scan.coverage.assessed / scan.coverage.total * 100) : 0;

  return <div className="vx-workspace" data-theme={theme}>
    <input ref={fileRef} type="file" accept=".json,application/json" className="sr-only" onChange={importFile} aria-label="Open VisionX report JSON" />
    <div className="vx-shell">
      {mobileOpen && <button className="vx-mobile-shade" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <aside className={`vx-sidebar ${mobileOpen ? "vx-sidebar--open" : ""}`}>
        <div className="vx-sidebar-brand"><Link href="/" aria-label="VisionX home"><VisionXLogo size={28} showText textClassName="text-[19px]" /></Link><span>WORKSPACE</span></div>
        <button className="vx-workspace-picker" onClick={() => selectView("overview")}><span className="vx-picker-mark"><Shield size={15} /></span><span><strong>Vision assurance</strong><small>Local review workspace</small></span><ChevronDown size={14} /></button>
        <button className="vx-search-trigger" onClick={() => setPaletteOpen(true)}><Search size={15} /><span>Search workspace</span><kbd>⌘ K</kbd></button>
        <div className="vx-sidebar-scroll">
          <p className="vx-nav-caption">WORKSPACE</p>
          <nav aria-label="Workspace navigation">{navigation.map(item => <button key={item.id} className={`vx-nav-link ${view === item.id ? "vx-nav-link--active" : ""}`} onClick={() => selectView(item.id)}><item.icon size={16} strokeWidth={1.8} /><span>{item.label}</span>{item.id === "findings" && scan.findings.length > 0 && <em>{scan.findings.length}</em>}</button>)}</nav>
          <div className="vx-sidebar-divider" />
          <div className="vx-nav-heading"><p className="vx-nav-caption">ASSESSMENTS</p><button title="Open report.json" aria-label="Open report JSON" onClick={() => fileRef.current?.click()}><Plus size={15} /></button></div>
          <div className="vx-scan-list">{scans.map(item => <button key={`${item.source}-${item.scan_id}`} onClick={() => selectScan(item.scan_id)} className={`vx-scan-link ${item.scan_id === scan.scan_id ? "vx-scan-link--active" : ""}`}><span className={`vx-scan-dot vx-scan-dot--${tone[disposition(item) ?? ""] ?? "muted"}`} /><span className="vx-scan-link-text"><strong>{item.name}</strong><small>{item.source === "server" ? "Server scan" : "Local report"} · {item.profile}</small></span></button>)}</div>
        </div>
        <div className="vx-sidebar-bottom"><div className="vx-local-indicator"><LockKeyhole size={14} /><span>{apiState === "connected" ? `Connected · ${session?.user.username}` : apiState === "signed-out" ? "Server available" : "Offline review"}</span><span className="vx-local-light" /></div>{apiState === "connected" && !session?.demo_mode && <button className="vx-back-link vx-signout" onClick={() => void signOut()}>Sign out of local server</button>}<Link href="/" className="vx-back-link"><ArrowLeft size={14} /> Back to site</Link></div>
      </aside>

      <div className="vx-body">
        <header className="vx-topbar"><div className="vx-topbar-left"><button className="vx-mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={19} /></button><span className="vx-topbar-crumb">Vision assurance</span><ChevronRight size={14} /><strong>{navigation.find(item => item.id === view)?.label}</strong><span className="vx-topbar-separator" /><span className="vx-topbar-scan">{scan.name}</span></div><div className="vx-topbar-actions"><button className="vx-topbar-local vx-connection-button" onClick={() => { if (apiState === "signed-out") setLoginOpen(true); else if (apiState === "connected") void refreshServer().then(() => setNotice("Server scans refreshed.")).catch(() => setNotice("Could not refresh server scans.")); }}><span /> {apiState === "connected" ? "Server connected" : apiState === "signed-out" ? "Sign in to server" : "Local only"}</button><button className="vx-theme-toggle" type="button" onClick={toggleTheme} aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"} aria-pressed={theme === "dark"} title={theme === "light" ? "Dark mode" : "Light mode"}>{theme === "light" ? <Moon size={17} /> : <Sun size={17} />}</button><button className="vx-icon-button" title={inspectorOpen ? "Hide details" : "Show details"} aria-label={inspectorOpen ? "Hide details" : "Show details"} onClick={() => setInspectorOpen(current => !current)}>{inspectorOpen ? <PanelRightClose size={17} /> : <PanelRightOpen size={17} />}</button><button className="vx-button vx-button--quiet vx-import-top" onClick={() => fileRef.current?.click()}><FolderOpen size={15} /> Open report</button><button className="vx-button vx-button--primary" onClick={() => setNewScanOpen(true)}><Plus size={16} /> New assessment</button></div></header>
        <div className="vx-content-row">
          <div className="vx-main-scroll" ref={mainRef}>
            <div className="vx-page">
              <div className="vx-page-heading"><div><div className="vx-overline"><span className="vx-overline-line" /> {view === "overview" ? "ASSESSMENT OVERVIEW" : `ASSESSMENT / ${view.toUpperCase()}`}</div><h1>{view === "overview" ? scan.name : navigation.find(item => item.id === view)?.label}</h1><p>{view === "overview" ? "Investigate what the engine observed, what ran, and what remains unknown." : descriptions[view]}</p></div><div className="vx-heading-actions"><Badge value={disposition(scan) ?? "UNKNOWN"}>{disposition(scan) ? label(disposition(scan)!) : label(scan.status)}</Badge><button className="vx-icon-button" title="Assessment details" aria-label="Assessment details" onClick={() => openInspector({ kind: "scan" })}><SlidersHorizontal size={17} /></button></div></div>
              {scan.source === "server" && !scan.coverage.rows.length && <div className="vx-demo-note"><Activity size={16} /><span><strong>{label(scan.status)}.</strong> The local server has not published a detailed result for this assessment yet. The workspace refreshes server scans automatically.</span><button onClick={() => void refreshServer().catch(() => setNotice("Could not refresh server scans."))}>Refresh <ArrowRight size={14} /></button></div>}
              {view === "overview" && <>
                <div className="vx-metrics"><Metric label="Findings needing attention" value={String(attentionCount).padStart(2, "0")} note={`${scan.findings.length} total findings`} icon={<ShieldAlert size={18} />} accent="rose" /><Metric label="Fully assessed classes" value={`${scan.coverage.assessed}/${scan.coverage.total}`} note={`${coveragePercent}% of listed classes`} icon={<CircleDashed size={18} />} accent="mint" /><Metric label="Detector execution" value={`${scan.summary?.detectors_completed ?? scan.executions.filter(item => item.state === "COMPLETED").length}`} note={`${scan.executions.length} planned checks`} icon={<Activity size={18} />} accent="blue" /><Metric label="Evidence records" value={String(evidence.length).padStart(2, "0")} note="Linked to findings" icon={<Fingerprint size={18} />} accent="pink" /></div>
                <div className="vx-overview-grid"><section className="vx-panel vx-priority-panel"><SectionTitle eyebrow="TRIAGE QUEUE" title="Needs your attention" action={<button className="vx-text-action" onClick={() => selectView("findings")}>All findings <ArrowRight size={14} /></button>} />{scan.findings.length ? <div className="vx-list">{scan.findings.slice(0, 4).map(finding => <button className="vx-finding-row" key={finding.id} onClick={() => openInspector({ kind: "finding", id: finding.id })}><span className={`vx-priority-stripe vx-priority-stripe--${tone[finding.recommended_disposition]}`} /><span className="vx-finding-main"><span className="vx-finding-meta">{finding.id} <span>·</span> {finding.detector_id}</span><strong>{finding.title}</strong><small>{finding.reason}</small></span><Badge value={finding.recommended_disposition} /><RowArrow /></button>)}</div> : <Empty title="No findings in this report" text="The engine did not emit findings for this assessment. Review coverage before drawing conclusions." />}</section><section className="vx-panel vx-coverage-panel"><SectionTitle eyebrow="ASSURANCE SCOPE" title="Coverage, not a score" action={<button className="vx-text-action" onClick={() => selectView("coverage")}>View matrix <ArrowRight size={14} /></button>} /><p className="vx-panel-description">Coverage states show which attack classes were assessed and which still need access or evidence.</p><CoverageBar scan={scan} /><div className="vx-coverage-legend">{(["ASSESSED", "PARTIALLY_ASSESSED", "NOT_ASSESSED", "FAILED_TO_EXECUTE", "UNSUPPORTED"] as CoverageState[]).map(state => <div key={state}><span className={`vx-legend-dot vx-legend-dot--${tone[state]}`} /><span>{label(state)}</span><strong>{coverageCount(scan, state)}</strong></div>)}</div></section></div>
                <div className="vx-overview-grid vx-overview-grid--lower"><section className="vx-panel"><SectionTitle eyebrow="EXECUTION PLAN" title="Detector outcomes" action={<button className="vx-text-action" onClick={() => selectView("detectors")}>All checks <ArrowRight size={14} /></button>} /><div className="vx-compact-list">{scan.executions.slice(0, 5).map(item => <button key={item.detector_id} className="vx-compact-row" onClick={() => openInspector({ kind: "execution", id: item.detector_id })}><span className={`vx-state-symbol vx-state-symbol--${tone[item.state] ?? "muted"}`}>{item.state === "COMPLETED" ? <Check size={13} /> : item.state === "ERROR" ? <X size={13} /> : <CircleDashed size={13} />}</span><span><strong>{item.title}</strong><small>{item.detector_id}</small></span><Badge value={item.state} /></button>)}</div></section><section className="vx-panel"><SectionTitle eyebrow="NEXT STEP" title="Keep the decision grounded" /><div className="vx-next-step"><div className="vx-next-icon"><GitBranch size={20} /></div><h3>Review gaps before disposition</h3><p>{scan.coverage.total - scan.coverage.assessed} attack classes are not fully assessed. Inspect their reasons and the additional evidence needed before making a decision.</p><button className="vx-button vx-button--outline" onClick={() => selectView("coverage")}>Inspect coverage gaps <ArrowRight size={15} /></button></div></section></div>
              </>}

              {view === "findings" && <section className="vx-panel vx-table-panel"><div className="vx-table-toolbar"><div><h2>Findings <span>{scan.findings.length}</span></h2><p>Evidence-first observations and policy dispositions</p></div><div className="vx-segmented">{["ALL", "QUARANTINE", "REVIEW", "ACCEPT"].map(item => <button key={item} className={findingFilter === item ? "active" : ""} onClick={() => setFindingFilter(item)}>{item === "ALL" ? "All" : label(item)}</button>)}</div></div>{filteredFindings.length ? <div className="vx-table-wrap"><table className="vx-table"><thead><tr><th>Finding</th><th>Detector</th><th>Severity</th><th>Disposition</th><th>Evidence</th><th /></tr></thead><tbody>{filteredFindings.map(item => <tr key={item.id} onClick={() => openInspector({ kind: "finding", id: item.id })}><td><div className="vx-table-primary">{item.title}</div><div className="vx-table-secondary">{item.id} · {item.attack_class}</div></td><td className="vx-mono">{item.detector_id}</td><td><Badge value={item.severity} /></td><td><Badge value={item.recommended_disposition} /></td><td>{item.evidence.length} record{item.evidence.length === 1 ? "" : "s"}</td><td><RowArrow /></td></tr>)}</tbody></table></div> : <Empty title="No findings match this view" text="Choose another disposition to see the remaining findings." />}</section>}

              {view === "coverage" && <><div className="vx-coverage-intro vx-panel"><div><span className="vx-eyebrow">ASSESSMENT BOUNDARY</span><h2>{scan.coverage.assessed} of {scan.coverage.total} classes fully assessed</h2><p>Unassessed and unsupported classes remain visible. A missing check is never represented as a pass.</p></div><CoverageBar scan={scan} /></div><section className="vx-panel vx-table-panel"><div className="vx-table-toolbar"><div><h2>Coverage matrix</h2><p>Computed from the plan and completed executions</p></div><select value={coverageFilter} onChange={event => setCoverageFilter(event.target.value)} aria-label="Filter coverage state" className="vx-select"><option value="ALL">All states</option>{(["ASSESSED", "PARTIALLY_ASSESSED", "NOT_ASSESSED", "FAILED_TO_EXECUTE", "UNSUPPORTED"] as CoverageState[]).map(item => <option key={item} value={item}>{label(item)}</option>)}</select></div>{filteredCoverage.length ? <div className="vx-table-wrap"><table className="vx-table"><thead><tr><th>Attack class</th><th>Layer</th><th>Assessment state</th><th>Detectors</th><th /></tr></thead><tbody>{filteredCoverage.map(item => <tr key={item.attack_class} onClick={() => openInspector({ kind: "coverage", id: item.attack_class })}><td><div className="vx-table-primary">{item.title}</div><div className="vx-table-secondary vx-mono">{item.attack_class}</div></td><td>{label(item.layer)}</td><td><Badge value={item.state} /></td><td className="vx-mono">{item.detectors.length ? item.detectors.join(", ") : "—"}</td><td><RowArrow /></td></tr>)}</tbody></table></div> : <Empty title="No classes match" text="Try another coverage state." />}</section></>}

              {view === "detectors" && <section className="vx-panel vx-table-panel"><div className="vx-table-toolbar"><div><h2>Detector execution <span>{scan.executions.length}</span></h2><p>Planned availability stays separate from the final execution state.</p></div></div>{scan.executions.length ? <div className="vx-table-wrap"><table className="vx-table"><thead><tr><th>Detector</th><th>Layer</th><th>Planned</th><th>Final state</th><th>Findings</th><th /></tr></thead><tbody>{scan.executions.map(item => <tr key={item.detector_id} onClick={() => openInspector({ kind: "execution", id: item.detector_id })}><td><div className="vx-table-primary">{item.title}</div><div className="vx-table-secondary vx-mono">{item.detector_id}</div></td><td>{label(item.layer)}</td><td><Badge value={item.planned} /></td><td><Badge value={item.state} /></td><td>{item.findings ?? 0}</td><td><RowArrow /></td></tr>)}</tbody></table></div> : <Empty title="No execution records" text="This report does not include a detector plan." />}</section>}

              {view === "evidence" && <><div className="vx-evidence-note"><LockKeyhole size={16} /><span>Evidence summaries are included in report.json. Large content-addressed blobs remain in the local evidence store and are not embedded here.</span></div>{evidence.length ? <div className="vx-evidence-grid">{evidence.map(item => <button key={`${item.finding.id}-${item.id}`} className="vx-evidence-card" onClick={() => openInspector({ kind: "finding", id: item.finding.id })}><span className="vx-evidence-glyph"><FileJson2 size={19} /></span><span className="vx-eyebrow">{label(item.kind)} · {item.finding.id}</span><strong>{item.title}</strong><p>{item.summary}</p><span className="vx-evidence-link">View linked finding <ArrowRight size={14} /></span></button>)}</div> : <Empty title="No evidence records" text="Findings in this assessment have no embedded evidence summaries." />}</>}

              {view === "assets" && <section className="vx-panel vx-table-panel"><div className="vx-table-toolbar"><div><h2>Assessment assets <span>{scan.assets.length}</span></h2><p>Inputs and references supplied to the engine</p></div></div>{scan.assets.length ? <div className="vx-table-wrap"><table className="vx-table"><thead><tr><th>Asset</th><th>Role</th><th>Format</th><th>Digest</th><th /></tr></thead><tbody>{scan.assets.map(item => <tr key={item.asset_id} onClick={() => openInspector({ kind: "asset", id: item.asset_id })}><td><div className="vx-table-primary">{item.name}</div><div className="vx-table-secondary vx-mono">{item.asset_id}</div></td><td>{label(item.role)}</td><td>{item.format ?? "—"}</td><td className="vx-mono">{short(item.digest, 20)}</td><td><RowArrow /></td></tr>)}</tbody></table></div> : <Empty title="No assets recorded" text="This scan result contains no asset descriptors." />}</section>}

              {view === "provenance" && <><div className="vx-provenance-intro vx-panel"><span className="vx-provenance-mark"><GitBranch size={23} /></span><div><span className="vx-eyebrow">CHAIN OF CUSTODY</span><h2>Evidence has a history</h2><p>Ledger checks bind inference records to inputs, model identity, and a trust root. This view reflects the imported scan result; independent signature verification remains a CLI task.</p></div></div><div className="vx-overview-grid"><section className="vx-panel"><SectionTitle eyebrow="PROVENANCE COVERAGE" title="What was assessed" />{scan.coverage.rows.filter(row => row.layer === "PROVENANCE").length ? <div className="vx-compact-list">{scan.coverage.rows.filter(row => row.layer === "PROVENANCE").map(row => <button key={row.attack_class} className="vx-compact-row" onClick={() => openInspector({ kind: "coverage", id: row.attack_class })}><span className={`vx-state-symbol vx-state-symbol--${tone[row.state] ?? "muted"}`}><GitBranch size={13} /></span><span><strong>{row.title}</strong><small>{row.attack_class}</small></span><Badge value={row.state} /></button>)}</div> : <Empty title="No provenance classes" text="This report has no provenance coverage rows." />}</section><section className="vx-panel"><SectionTitle eyebrow="TRUST INPUTS" title="Supplied assets" />{scan.assets.filter(asset => ["INFERENCE_LEDGER", "TRUST_ROOT"].includes(asset.role)).length ? <div className="vx-compact-list">{scan.assets.filter(asset => ["INFERENCE_LEDGER", "TRUST_ROOT"].includes(asset.role)).map(asset => <button className="vx-compact-row" key={asset.asset_id} onClick={() => openInspector({ kind: "asset", id: asset.asset_id })}><span className="vx-state-symbol"><FileJson2 size={13} /></span><span><strong>{asset.name}</strong><small>{label(asset.role)}</small></span><RowArrow /></button>)}</div> : <Empty title="No ledger or trust root supplied" text="Add these inputs to a CLI scan to assess record integrity and binding." />}</section></div><section className="vx-panel"><SectionTitle eyebrow="DETECTOR EXECUTION" title="Ledger checks" />{scan.executions.filter(item => item.layer === "PROVENANCE").length ? <div className="vx-compact-list">{scan.executions.filter(item => item.layer === "PROVENANCE").map(item => <button className="vx-compact-row" key={item.detector_id} onClick={() => openInspector({ kind: "execution", id: item.detector_id })}><span className={`vx-state-symbol vx-state-symbol--${tone[item.state] ?? "muted"}`}><GitBranch size={13} /></span><span><strong>{item.title}</strong><small>{item.reasons?.join(" ") || item.detector_id}</small></span><Badge value={item.state} /></button>)}</div> : <Empty title="No provenance execution records" text="This assessment did not plan a provenance detector." />}</section></>}

              {view === "activity" && <section className="vx-panel vx-activity-panel"><SectionTitle eyebrow="EXECUTION TRACE" title="Assessment activity" /><p className="vx-panel-description">Events recorded by the engine for this scan. Times are relative to scan start.</p>{scan.events.length ? <div className="vx-timeline">{scan.events.map(event => <div className="vx-timeline-item" key={`${event.seq}-${event.t_ms}`}><span className={`vx-timeline-point vx-timeline-point--${event.level}`} /><span className="vx-mono vx-timeline-time">+{(event.t_ms / 1000).toFixed(2)}s</span><div><strong>{event.message}</strong>{event.detector_id && <small>{event.detector_id}</small>}</div></div>)}</div> : <Empty title="No events recorded" text="The imported scan result does not include an event trace." />}</section>}
              <div className="vx-page-foot"><span>VisionX · offline assurance review</span><span>{scan.source === "server" ? "VisionX backend result" : "Local report · never uploaded"}</span></div>
            </div>
          </div>
          {inspectorOpen && <>{inspectorOverlay && <button className="vx-inspector-shade" aria-label="Close details" onClick={() => setInspectorOverlay(false)} />}<aside className={`vx-inspector ${inspectorOverlay ? "vx-inspector--overlay" : ""}`}><InspectorPanel key={`${scan.scan_id}-${inspector?.kind}-${inspector && "id" in inspector ? inspector.id : ""}`} scan={scan} inspector={inspector} copy={copy} onClose={() => { setInspectorOpen(false); setInspectorOverlay(false); }} onView={selectView} /></aside></>}
        </div>
      </div>
    </div>

    {notice && <div className="vx-toast" role="status"><CheckCircle2 size={17} />{notice}<button aria-label="Dismiss" onClick={() => setNotice("")}><X size={14} /></button></div>}
    {paletteOpen && <div className="vx-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setPaletteOpen(false); }}><div className="vx-palette" role="dialog" aria-modal="true" aria-label="Search workspace"><div className="vx-palette-search"><Search size={19} /><input autoFocus value={query} onChange={event => setQuery(event.target.value)} placeholder="Search views and assessments..." /><kbd>ESC</kbd></div><div className="vx-palette-results"><span className="vx-eyebrow">VIEWS</span>{navigation.filter(item => item.label.toLowerCase().includes(query.toLowerCase())).map(item => <button key={item.id} onClick={() => { selectView(item.id); setQuery(""); }}><item.icon size={17} />{item.label}<ArrowRight size={14} /></button>)}<span className="vx-eyebrow">ASSESSMENTS</span>{scans.filter(item => `${item.name} ${item.scan_id}`.toLowerCase().includes(query.toLowerCase())).map(item => <button key={item.scan_id} onClick={() => { selectScan(item.scan_id); setQuery(""); }}><FileText size={17} />{item.name}<ArrowRight size={14} /></button>)}<button onClick={() => { setPaletteOpen(false); fileRef.current?.click(); }}><FolderOpen size={17} />Open report.json<ArrowRight size={14} /></button></div></div></div>}
    {newScanOpen && <NewAssessment onClose={() => setNewScanOpen(false)} copy={copy} session={session} profiles={serverProfiles} onQueue={queueServerScan} />}
    {loginOpen && <ServerLogin onClose={() => setLoginOpen(false)} onLogin={signIn} />}
  </div>;
}

const descriptions: Record<View, string> = {
  overview: "Investigate what the engine observed, what ran, and what remains unknown.",
  findings: "Triage observations, inspect supporting evidence, and understand recommended dispositions.",
  coverage: "See the exact boundaries of this assessment, including unavailable and unsupported checks.",
  detectors: "Review the plan, execution outcomes, and reasons for checks that could not run.",
  evidence: "Follow the evidence attached to each finding.",
  assets: "Inspect the model, datasets, references, and other inputs used for this assessment.",
  provenance: "Review ledger coverage, trust inputs, and cryptographic detector outcomes.",
  activity: "Trace how the assessment progressed from probing to report generation.",
};

function Metric({ label: title, value, note, icon, accent }: { label: string; value: string; note: string; icon: ReactNode; accent: string }) { return <div className="vx-metric"><div className="vx-metric-top"><span>{title}</span><span className={`vx-metric-icon vx-metric-icon--${accent}`}>{icon}</span></div><strong>{value}</strong><small>{note}</small></div>; }
function coverageCount(scan: WorkspaceScan, state: CoverageState) { return scan.coverage.rows.filter(row => row.state === state).length; }
function CoverageBar({ scan }: { scan: WorkspaceScan }) { const states: CoverageState[] = ["ASSESSED", "PARTIALLY_ASSESSED", "NOT_ASSESSED", "FAILED_TO_EXECUTE", "UNSUPPORTED"]; return <div className="vx-coverage-bar" role="img" aria-label={`${scan.coverage.assessed} of ${scan.coverage.total} classes fully assessed`}>{states.map(state => { const count = coverageCount(scan, state); return count > 0 ? <span key={state} className={`vx-coverage-segment vx-coverage-segment--${tone[state]}`} style={{ flex: count }} title={`${count} ${label(state)}`} /> : null; })}</div>; }

function InspectorPanel({ scan, inspector, copy, onClose, onView }: { scan: WorkspaceScan; inspector: Inspector | null; copy: (value: string, message?: string) => void; onClose: () => void; onView: (view: View) => void }) {
  const finding = inspector?.kind === "finding" ? scan.findings.find(item => item.id === inspector.id) : null;
  const coverage = inspector?.kind === "coverage" ? scan.coverage.rows.find(item => item.attack_class === inspector.id) : null;
  const execution = inspector?.kind === "execution" ? scan.executions.find(item => item.detector_id === inspector.id) : null;
  const asset = inspector?.kind === "asset" ? scan.assets.find(item => item.asset_id === inspector.id) : null;
  const heading = finding ? "Finding detail" : coverage ? "Coverage detail" : execution ? "Detector detail" : asset ? "Asset detail" : "Assessment context";
  return <><div className="vx-inspector-head"><span>INSPECTOR</span><button title="Close details" aria-label="Close details" onClick={onClose}><X size={17} /></button></div><div className="vx-inspector-scroll"><div className="vx-inspector-hero"><span className="vx-eyebrow">{heading}</span><h2>{finding?.title ?? coverage?.title ?? execution?.title ?? asset?.name ?? scan.name}</h2>{finding && <Badge value={finding.recommended_disposition} />}{coverage && <Badge value={coverage.state} />}{execution && <Badge value={execution.state} />}{!finding && !coverage && !execution && <Badge value={disposition(scan) ?? scan.status} />}</div>
    {finding && <><InspectorSection title="Observation"><p>{finding.reason}</p></InspectorSection><InspectorSection title="Classification"><Definition label="Finding ID" value={finding.id} /><Definition label="Severity" value={label(finding.severity)} /><Definition label="Confidence" value={`${Math.round(finding.confidence * 100)}%`} /><Definition label="Detector" value={finding.detector_id} /><Definition label="Attack class" value={finding.attack_class} /><Definition label="Affected samples" value={finding.affected_count?.toLocaleString() ?? "—"} /></InspectorSection><InspectorSection title={`Evidence · ${finding.evidence.length}`}>{finding.evidence.length ? finding.evidence.map(item => <div className="vx-inspector-evidence" key={item.id}><span className="vx-eyebrow">{label(item.kind)}</span><strong>{item.title}</strong><p>{item.summary}</p>{item.data && <pre>{JSON.stringify(item.data, null, 2)}</pre>}{item.blob && <small>Blob: {short(item.blob.digest, 28)} · {item.blob.media_type}</small>}</div>) : <p>No evidence records in this report.</p>}</InspectorSection>{finding.limitations?.length ? <InspectorSection title="Limitations">{finding.limitations.map(item => <p key={item} className="vx-inspector-bullet">{item}</p>)}</InspectorSection> : null}{finding.access_assumptions?.length ? <InspectorSection title="Required access"><p>{finding.access_assumptions.join(" · ")}</p></InspectorSection> : null}</>}
    {coverage && <><InspectorSection title="Why this state"><p>{coverage.reason}</p></InspectorSection><InspectorSection title="Assessment"><Definition label="Attack class" value={coverage.attack_class} /><Definition label="Layer" value={label(coverage.layer)} /><Definition label="Detectors" value={coverage.detectors.join(", ") || "None"} /></InspectorSection>{coverage.required_access?.length ? <InspectorSection title="Required access"><p>{coverage.required_access.join(" · ")}</p></InspectorSection> : null}{coverage.recommended_evidence?.length ? <InspectorSection title="Additional evidence">{coverage.recommended_evidence.map(item => <p key={item} className="vx-inspector-bullet">{item}</p>)}</InspectorSection> : null}</>}
    {execution && <><InspectorSection title="Execution state"><Definition label="Detector ID" value={execution.detector_id} /><Definition label="Layer" value={label(execution.layer)} /><Definition label="Planned" value={label(execution.planned)} /><Definition label="Final" value={label(execution.state)} /><Definition label="Mode" value={execution.mode ?? "—"} /><Definition label="Runtime" value={execution.runtime_ms != null ? `${execution.runtime_ms.toLocaleString()} ms` : "—"} /><Definition label="Samples" value={execution.samples_processed?.toLocaleString() ?? "—"} /><Definition label="Findings" value={String(execution.findings ?? 0)} /></InspectorSection>{execution.reasons?.length ? <InspectorSection title="Reasons">{execution.reasons.map(item => <p key={item} className="vx-inspector-bullet">{item}</p>)}</InspectorSection> : null}</>}
    {asset && <><InspectorSection title="Asset properties"><Definition label="Asset ID" value={asset.asset_id} /><Definition label="Role" value={label(asset.role)} /><Definition label="Format" value={asset.format ?? "—"} />{asset.details && Object.entries(asset.details).map(([key, value]) => <Definition key={key} label={label(key)} value={typeof value === "object" ? JSON.stringify(value) : String(value)} />)}</InspectorSection>{asset.digest && <InspectorSection title="Content digest"><div className="vx-digest">{asset.digest}</div><button className="vx-copy-action" onClick={() => copy(asset.digest!, "Asset digest copied")}><Clipboard size={14} /> Copy digest</button></InspectorSection>}</>}
    {!finding && !coverage && !execution && !asset && <><InspectorSection title="Report details"><Definition label="Scan ID" value={scan.scan_id || "—"} /><Definition label="Profile" value={scan.profile || "—"} /><Definition label="Budget" value={label(scan.budget) || "—"} /><Definition label="Status" value={label(scan.status) || "—"} /><Definition label="Created" value={date(scan.created_at)} /><Definition label="Completed" value={date(scan.completed_at)} /><Definition label="Source" value={scan.source === "server" ? "VisionX backend" : "Locally opened report.json"} /></InspectorSection><InspectorSection title="Assessment boundary"><p>{scan.coverage.assessed} of {scan.coverage.total} listed attack classes fully assessed. {scan.coverage.partial} partially assessed; {scan.coverage.not_assessed} not assessed.</p><button className="vx-copy-action" onClick={() => onView("coverage")}>View coverage matrix <ArrowRight size={14} /></button></InspectorSection>{scan.report_digest && <InspectorSection title="Report digest"><div className="vx-digest">{scan.report_digest}</div><button className="vx-copy-action" onClick={() => copy(scan.report_digest!, "Report digest copied")}><Clipboard size={14} /> Copy digest</button></InspectorSection>}</>}
    <div className="vx-inspector-disclaimer"><Shield size={15} /><span>Cryptographic verification requires the CLI verifier and trust root.</span></div>
  </div></>;
}
function InspectorSection({ title, children }: { title: string; children: ReactNode }) { return <section className="vx-inspector-section"><h3>{title}</h3>{children}</section>; }
function Definition({ label: title, value }: { label: string; value: string }) { return <div className="vx-definition"><span>{title}</span><strong>{value}</strong></div>; }

function NewAssessment({ onClose, copy, session, profiles, onQueue }: { onClose: () => void; copy: (value: string, message?: string) => void; session: ApiSession | null; profiles: ApiProfile[]; onQueue: (body: { name: string; profile: string; dataset?: string; model?: string }) => Promise<void> }) {
  const canRun = session && ["ANALYST", "APPROVER", "ADMIN"].includes(session.user.role);
  const [mode, setMode] = useState<"server" | "cli">(canRun ? "server" : "cli");
  const [profile, setProfile] = useState(profiles[0]?.name ?? "");
  const [dataset, setDataset] = useState("./data/dataset");
  const [model, setModel] = useState("./models/candidate.onnx");
  const [name, setName] = useState("New assessment");
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [modelId, setModelId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { if (!profile && profiles[0]) setProfile(profiles[0].name); }, [profile, profiles]);
  useEffect(() => { if (canRun) void loadServerAssets().then(setAssets).catch(() => setError("Could not load registered assets from the local server.")); }, [canRun]);
  useEffect(() => { if (profiles.length && !profiles.some(item => item.name === profile)) setProfile(profiles[0].name); }, [profiles, profile]);
  const shellArg = (value: string) => `'${value.replaceAll("'", "'\\''")}'`;
  const command = `visionsentinel scan --dataset ${shellArg(dataset.trim() || "<dataset-path>")} --model ${shellArg(model.trim() || "<model-path>")} --profile ${profile || "<profile>"} --out <reports-directory>`;
  const queue = async () => {
    if (!datasetId && !modelId) { setError("Choose at least one registered asset."); return; }
    setError(""); setSubmitting(true);
    try { await onQueue({ name: name.trim() || "assessment", profile, ...(datasetId ? { dataset: datasetId } : {}), ...(modelId ? { model: modelId } : {}) }); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not queue assessment."); }
    finally { setSubmitting(false); }
  };
  return <div className="vx-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><div className="vx-new-modal" role="dialog" aria-modal="true" aria-label="New assessment"><div className="vx-new-modal-head"><div className="vx-new-modal-icon"><Terminal size={20} /></div><button aria-label="Close" onClick={onClose}><X size={18} /></button></div><span className="vx-eyebrow">ASSESSMENT WORKFLOW</span><h2>Start a new assessment</h2><p>{canRun ? "Queue a scan using registered assets on the VisionX backend, or copy a command to run in your terminal." : "Run the VisionX CLI locally, then open the resulting report.json here. Sign in with an analyst account to queue scans through the VisionX backend."}</p>{canRun && <div className="vx-mode-switch"><button className={mode === "server" ? "active" : ""} onClick={() => setMode("server")}>VisionX backend</button><button className={mode === "cli" ? "active" : ""} onClick={() => setMode("cli")}>Terminal command</button></div>}
    {mode === "server" && canRun ? <><label>Assessment name<input value={name} onChange={event => setName(event.target.value)} maxLength={120} /></label><label>Dataset asset<select value={datasetId} onChange={event => setDatasetId(event.target.value)}><option value="">None</option>{assets.filter(item => item.kind === "dataset").map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Model asset<select value={modelId} onChange={event => setModelId(event.target.value)}><option value="">None</option>{assets.filter(item => item.kind === "model").map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Assessment profile<select value={profile} onChange={event => setProfile(event.target.value)}>{profiles.length ? profiles.map(item => <option key={item.name} value={item.name}>{item.name} · {item.budget}</option>) : <option value="" disabled>No backend profiles available</option>}</select></label><div className="vx-new-modal-actions"><button className="vx-button vx-button--quiet" onClick={onClose}>Cancel</button><button className="vx-button vx-button--primary" disabled={submitting || !profile || (!datasetId && !modelId)} onClick={() => void queue()}><Plus size={15} /> {submitting ? "Queuing…" : "Queue assessment"}</button></div><div className="vx-new-note"><LockKeyhole size={15} /> Assets and scan results stay on the local server.</div></> : <><label>Dataset path<input value={dataset} onChange={event => setDataset(event.target.value)} spellCheck={false} /></label><label>Model path<input value={model} onChange={event => setModel(event.target.value)} spellCheck={false} /></label><label>Assessment profile<select value={profile} onChange={event => setProfile(event.target.value)}>{profiles.length ? profiles.map(item => <option key={item.name} value={item.name}>{item.name} · {item.budget}</option>) : <option value="" disabled>No backend profiles available</option>}</select></label><div className="vx-command-preview"><span>TERMINAL COMMAND</span><code>{command}</code></div><div className="vx-new-modal-actions"><button className="vx-button vx-button--quiet" onClick={onClose}>Cancel</button><button className="vx-button vx-button--primary" disabled={!profile} onClick={() => copy(command, "Command copied. Run it in your local terminal.")}><Clipboard size={15} /> Copy command</button></div><div className="vx-new-note"><CircleAlert size={15} /> The browser only prepares this command. Run it in your local terminal.</div></>}{error && <p className="vx-form-error" role="alert">{error}</p>}</div></div>;
}

function ServerLogin({ onClose, onLogin }: { onClose: () => void; onLogin: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async () => {
    setBusy(true); setError("");
    try { await onLogin(username.trim(), password); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Sign in failed."); }
    finally { setBusy(false); }
  };
  return <div className="vx-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><form className="vx-new-modal" role="dialog" aria-modal="true" aria-label="Sign in to VisionX backend" onSubmit={event => { event.preventDefault(); void submit(); }}><div className="vx-new-modal-head"><div className="vx-new-modal-icon"><LockKeyhole size={20} /></div><button type="button" aria-label="Close" onClick={onClose}><X size={18} /></button></div><span className="vx-eyebrow">VISIONX BACKEND</span><h2>Sign in to VisionX</h2><p>Use an account on the VisionX backend to review server scans and, with analyst access, queue assessments.</p><label>Username<input autoFocus autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} required /></label><label>Password<input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required /></label>{error && <p className="vx-form-error" role="alert">{error}</p>}<div className="vx-new-modal-actions"><button type="button" className="vx-button vx-button--quiet" onClick={onClose}>Cancel</button><button type="submit" disabled={busy} className="vx-button vx-button--primary">{busy ? "Signing in…" : "Sign in"}</button></div></form></div>;
}
