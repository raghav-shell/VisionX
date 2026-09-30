"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowRight, Check, CircleAlert, LoaderCircle, Play, ShieldCheck, Upload, X } from "lucide-react";
import type { ApiAsset, ApiEvidenceGraph, ApiFindingDetail, ApiGraphNode, ApiHistoryEvent, ApiJob, ApiMetadata, ApiProfile, ApiScenario, ScanRequestBody } from "./workspace-api";
import { acknowledgeFinding, assignFinding, commentFinding, decide, loadFinding, loadFindingHistory, loadJob, loadScanGraph, loadScenarios, requestFindingDecision, runScenario, submitServerScan, uploadServerAsset } from "./workspace-api";
import { prose } from "./workspace-data";

const humanize = (value: string) => value.replaceAll("_", " ").toLowerCase();



export function AdvancedAssessment({ onClose, onRequireAuth, directDemo, csrf, metadata, assets, profiles, onQueued, onAssetUploaded }: { onClose: () => void; onRequireAuth: () => void; directDemo: boolean; csrf: string | null; metadata: ApiMetadata | null; assets: ApiAsset[]; profiles: ApiProfile[]; onQueued: (scanId: string) => void; onAssetUploaded: (asset: ApiAsset) => void }) {
  const [name, setName] = useState("");
  const [profile, setProfile] = useState("");
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { if (!profile && profiles[0]) setProfile(profiles[0].name); }, [profile, profiles]);
  const inputs = metadata?.asset_inputs ?? [];
  const queue = async () => {
    if ((!csrf && !directDemo) || !profile) return;
    const fields = Object.fromEntries(Object.entries(selected).filter(([, value]) => value));
    if (!Object.keys(fields).length) { setError("Select at least one registered input asset."); return; }
    setBusy(true); setError("");
    try { onQueued(await submitServerScan({ name: name.trim() || "assessment", profile, ...fields } as ScanRequestBody, csrf ?? "")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not queue the assessment."); }
    finally { setBusy(false); }
  };
  return <div className="vx-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><form className="vx-new-modal" role="dialog" aria-modal="true" aria-label="New backend assessment" onSubmit={event => { event.preventDefault(); void queue(); }}>
    <div className="vx-new-modal-head"><div className="vx-new-modal-icon"><ShieldCheck size={20} /></div><button type="button" aria-label="Close" onClick={onClose}><X size={18} /></button></div>
    <span className="vx-eyebrow">BACKEND ASSESSMENT</span><h2>Start a real assessment</h2><p>Choose registered assets. The backend validates compatibility and resolves the current ScanRequest contract.</p>
    <label>Assessment name<input value={name} onChange={event => setName(event.target.value)} placeholder="Optional name" /></label>
    <label>Profile<select value={profile} onChange={event => setProfile(event.target.value)} required><option value="" disabled>Select a backend profile</option>{profiles.map(item => <option key={item.name} value={item.name}>{item.name} · {item.budget}</option>)}</select></label>
    <button type="button" className="vx-advanced-toggle" aria-expanded={advanced} onClick={() => setAdvanced(value => !value)}>{advanced ? "Hide" : "Show"} advanced inputs <ArrowRight size={14} /></button>
    <div className="vx-asset-role-grid"><AssetRole field={inputs[0]} assets={assets} csrf={csrf} value={selected[inputs[0]?.field ?? ""] ?? ""} onChange={(field, value) => setSelected(current => ({ ...current, [field]: value }))} onAssetImported={(field, asset) => { onAssetUploaded(asset); setSelected(current => ({ ...current, [field]: asset.id })); }} /></div>
    {advanced && <div className="vx-asset-role-grid">{inputs.slice(1).map(input => <AssetRole key={input.field} field={input} assets={assets} csrf={csrf} value={selected[input.field] ?? ""} onChange={(field, value) => setSelected(current => ({ ...current, [field]: value }))} onAssetImported={(field, asset) => { onAssetUploaded(asset); setSelected(current => ({ ...current, [field]: asset.id })); }} />)}</div>}
    {error && <p className="vx-form-error" role="alert">{error}</p>}
    <div className="vx-new-modal-actions"><button type="button" className="vx-button vx-button--quiet" onClick={onClose}>Cancel</button><button type={csrf || directDemo ? "submit" : "button"} className="vx-button vx-button--primary" disabled={busy || !profile} onClick={csrf || directDemo ? undefined : onRequireAuth}>{busy ? "Queuing…" : csrf || directDemo ? "Queue assessment" : "Sign in to queue"}<Play size={14} /></button></div>
    <div className="vx-new-note"><ShieldCheck size={15} /> {directDemo ? "LOCAL DEMO · ANALYST: localhost-only assessment mode." : csrf ? "No filesystem paths are accepted by this browser workflow." : "Sign in to the VisionX backend before queueing an assessment."}</div>
  </form></div>;
}

function AssetRole({ field, assets, csrf, value, onChange, onAssetImported }: { field?: ApiMetadata["asset_inputs"][number]; assets: ApiAsset[]; csrf: string | null; value: string; onChange: (field: string, value: string) => void; onAssetImported: (field: string, asset: ApiAsset) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  if (!field) return <p className="vx-form-help">No asset roles are currently published by the backend.</p>;
  const compatible = assets.filter(asset => field.compatible_kinds.includes(asset.kind));
  const kind = field.compatible_kinds[0];
  const upload = async () => {
    if (!file || !kind || !csrf) return;
    setUploading(true); setUploadError("");
    try { onAssetImported(field.field, await uploadServerAsset(file, kind, csrf)); setFile(null); }
    catch (cause) { setUploadError(cause instanceof Error ? cause.message : "Could not register the selected asset."); }
    finally { setUploading(false); }
  };
  const unique = [...new Map(compatible.map(asset => [asset.digest ? `${asset.kind}:${asset.digest}` : asset.id, asset])).values()];
  return <div className="vx-asset-role"><label>{humanize(field.field)}<select value={value} onChange={event => onChange(field.field, event.target.value)}><option value="">Not supplied</option>{unique.map(asset => <option key={asset.id} value={asset.id}>{asset.name} · {asset.kind}{asset.digest ? ` · ${asset.digest.slice(0, 12)}…` : ""}</option>)}</select></label>{!compatible.length && <div className="vx-asset-import" role="group" aria-label={`Register ${humanize(field.field)} asset`}><small className="vx-form-help">No active compatible assets registered. Choose a file or archive to have the backend validate and register it.</small><input type="file" aria-label={`Choose ${humanize(field.field)} asset file`} onChange={event => { setFile(event.target.files?.[0] ?? null); setUploadError(""); }} /><button type="button" className="vx-button vx-button--quiet" disabled={!file || !kind || !csrf || uploading} onClick={() => void upload()}><Upload size={14} />{uploading ? "Registering…" : `Register ${humanize(kind)}`}</button>{uploadError && <small className="vx-form-error" role="alert">{uploadError}</small>}</div>}</div>;
}

/** A scenario manifest value as a short phrase: nested sections are summarised, not printed as [object Object]. */
function describeValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (Array.isArray(value)) {
    const names = value.map(item => (item && typeof item === "object" && "name" in item ? String((item as { name: unknown }).name) : null)).filter(Boolean);
    return names.length === value.length && names.length > 0 ? names.join(", ") : `${value.length} item${value.length === 1 ? "" : "s"}`;
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, inner]) => `${humanize(key)} ${inner !== null && typeof inner === "object" ? describeValue(inner) : String(inner)}`)
      .join(", ");
  }
  return String(value);
}

/** State words as chips: dispositions, governance and job states. Hue carries state only. */
const stateTone: Record<string, string> = {
  QUARANTINE: "rose", REVIEW: "amber", ACCEPT: "mint",
  OPEN: "blue", ACKNOWLEDGED: "blue", PENDING_DECISION: "amber", DECIDED: "mint",
  PENDING: "amber", APPROVED: "mint", APPLIED: "mint", REJECTED: "rose",
  QUEUED: "blue", RUNNING: "blue", COMPLETED: "mint", FAILED: "rose",
};
function Chip({ value }: { value: string }) {
  return <span className={`vx-badge vx-badge--${stateTone[value] ?? "muted"}`}>{humanize(value)}</span>;
}
function when(value?: string | null) {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function AttackLabView({ csrf, directDemo, profiles, metadata, onOpenScan }: { csrf: string | null; directDemo: boolean; profiles: ApiProfile[]; metadata: ApiMetadata | null; onOpenScan: (scanId: string) => void }) {
  const [scenarios, setScenarios] = useState<ApiScenario[]>([]);
  const [selected, setSelected] = useState("");
  const [job, setJob] = useState<ApiJob | null>(null);
  const [error, setError] = useState("");
  const [profile, setProfile] = useState("");
  useEffect(() => { void loadScenarios().then(items => { setScenarios(items); setSelected(current => current || items[0]?.scenario_id || ""); }).catch(cause => setError(cause instanceof Error ? cause.message : "Could not load scenarios.")); }, []);
  useEffect(() => { if (!profile && profiles[0]) setProfile(profiles[0].name); }, [profile, profiles]);
  useEffect(() => { if (!job || job.terminal || !metadata) return; let cancelled = false; const timer = window.setTimeout(() => { void loadJob(job.id).then(next => { if (!cancelled) setJob(next); }).catch(() => undefined); }, metadata.job_poll_interval_ms); return () => { cancelled = true; window.clearTimeout(timer); }; }, [job, metadata]);
  const scenario = useMemo(() => scenarios.find(item => item.scenario_id === selected), [scenarios, selected]);
  const start = async () => { if ((!csrf && !directDemo) || !selected || !profile) return; try { setError(""); const queued = await runScenario(selected, profile, csrf ?? ""); setJob(await loadJob(queued.job_id)); } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not start the scenario."); } };
  const selectScenario = (value: string) => { setSelected(value); setJob(null); setError(""); };
  const selectProfile = (value: string) => { setProfile(value); setJob(null); setError(""); };
  const facts = scenario ? Object.entries(scenario).filter(([key]) => !["scenario_id", "title", "description"].includes(key)) : [];
  return <section className="vx-panel vx-workflow-panel">
    <div className="vx-section-title"><div><span>CONTROLLED EXPERIMENTS</span><h2>Attack Lab</h2><p className="vx-section-subtitle">Run a declared experiment against registered assets and follow its evidence-backed result.</p></div><Activity size={18} /></div>
    <div className="vx-workflow-body">
      <label>Scenario<select value={selected} onChange={event => selectScenario(event.target.value)} aria-label="Attack Lab scenario">{scenarios.map(item => <option key={item.scenario_id} value={item.scenario_id}>{item.title}</option>)}</select></label>
      {scenario && <div className="vx-workflow-summary"><strong>{scenario.title}</strong><p>{prose(scenario.description ?? "Scenario metadata supplied by the backend.")}</p>{facts.length > 0 && <dl className="vx-workflow-facts">{facts.map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{prose(describeValue(value))}</dd></div>)}</dl>}</div>}
      <div className="vx-workflow-run"><label>Profile<select value={profile} onChange={event => selectProfile(event.target.value)} aria-label="Attack Lab profile">{profiles.map(item => <option key={item.name} value={item.name}>{item.name} · {item.budget}</option>)}</select></label><button className="vx-button vx-button--primary" disabled={(!csrf && !directDemo) || !selected || !profile || Boolean(job && !job.terminal)} onClick={() => void start()}><Play size={14} /> {job && !job.terminal ? "Running…" : "Run scenario"}</button></div>
      {error && <p className="vx-form-error" role="alert">{error}</p>}
      {job && <JobProgress job={job} onOpenScan={onOpenScan} />}
    </div>
  </section>;
}

function JobProgress({ job, onOpenScan }: { job: ApiJob; onOpenScan: (scanId: string) => void }) {
  const running = !job.terminal;
  return <div className={`vx-job-progress ${running ? "vx-job-progress--running" : ""}`} aria-live="polite">
    <div className="vx-job-head"><span><strong>{job.kind}</strong> · {job.subject}</span><Chip value={job.status} /></div>
    {running && <span className="vx-scan-rule" aria-hidden="true" />}
    {job.steps.length ? <ol>{job.steps.map((step, index) => <li key={`${step.name ?? "step"}-${index}`}><span className="vx-job-dot">{job.terminal ? <Check size={12} /> : <LoaderCircle size={12} />}</span><span><strong>{step.name ?? "step"}</strong>{step.detail && <small>{prose(step.detail)}</small>}</span></li>)}</ol> : <p>Waiting for the worker to publish its first step.</p>}
    {job.error && <p className="vx-form-error">The backend reported a safe job failure: {job.error}</p>}
    {job.scan_id && <button className="vx-button vx-button--outline" onClick={() => onOpenScan(job.scan_id!)}>Open linked scan <ArrowRight size={14} /></button>}
  </div>;
}

/* ------------------------------------------------------------------ evidence graph */

/** Columns of the graph, left to right: what supports a finding, the findings, what they are about, where that came from, what flagged it. */
const GRAPH_COLUMNS: { title: string; types: string[]; weight: number }[] = [
  { title: "Evidence", types: ["Evidence", "Signal"], weight: 1.15 },
  { title: "Findings", types: ["Finding", "Decision"], weight: 1.45 },
  { title: "Subjects", types: ["Sample", "InferenceRecord", "Class"], weight: 1 },
  { title: "Sources", types: ["Contributor", "Dataset", "Asset", "Model"], weight: 1 },
  { title: "Detectors", types: ["Detector"], weight: 1.1 },
];
/** Types the contract may add later land with the sources. */
const OTHER_COLUMN = 3;
/** Identifiers read better in mono. */
const MONO_TYPES = new Set(["Sample", "InferenceRecord"]);
const PLURAL: Record<string, string> = { Evidence: "Evidence", Finding: "Findings", Detector: "Detectors", Sample: "Samples", Contributor: "Contributors", Dataset: "Datasets" };

type PlacedNode = { node: ApiGraphNode; col: number; x: number; y: number; w: number; h: number; lines: string[]; mono: boolean; isolated: boolean };
type NodeRelation = { dir: "out" | "in"; type: string; count: number };
type GraphLayout = {
  width: number; height: number;
  columns: { key: string; title: string; x: number; count: number }[];
  headers: { key: string; x: number; y: number; text: string }[];
  nodes: PlacedNode[];
  edges: { source: string; target: string; d: string }[];
  neighbours: Map<string, Set<string>>;
  relations: { type: string; from: string; to: string; count: number }[];
  nodeRelations: Map<string, NodeRelation[]>;
};

/** Shorten a label to max characters: prose at a word boundary, identifiers in the middle so both ends stay readable. */
function clip(text: string, max: number, middle: boolean): string {
  if (text.length <= max) return text;
  if (middle) { const head = Math.ceil((max - 1) / 2); return `${text.slice(0, head)}…${text.slice(text.length - (max - 1 - head))}`; }
  const cut = text.slice(0, max - 1);
  const space = cut.lastIndexOf(" ");
  return `${(space > max * 0.55 ? cut.slice(0, space) : cut).replace(/[\s,.:;('-]+$/, "")}…`;
}
/** Two lines at most, the second clipped. A trailing "(sample-id)" is kept whole: it is what tells two findings apart. */
function wrapTwo(text: string, max: number): string[] {
  if (text.length <= max) return [text];
  let first = "";
  for (const word of text.split(" ")) { const next = first ? `${first} ${word}` : word; if (next.length > max) break; first = next; }
  if (!first) return [clip(text, max, false)];
  const rest = text.slice(first.length).trim();
  const open = rest.lastIndexOf(" (");
  if (rest.length > max && rest.endsWith(")") && open > 0 && rest.length - open < max - 6) {
    const suffix = rest.slice(open + 1);
    return [first, `${clip(rest.slice(0, open), max - suffix.length - 1, false)} ${suffix}`];
  }
  return [first, clip(rest, max, false)];
}

function layoutGraph(graph: ApiEvidenceGraph, width: number): GraphLayout {
  const PAD = 12, GAP = width < 900 ? 24 : 30, TOP = 40, ROW = 24, NODE_H = 18, ROW_TALL = 42, NODE_TALL = 34, SUBHEAD = 20;
  const ids = new Set(graph.nodes.map(node => node.id));
  const neighbours = new Map<string, Set<string>>(graph.nodes.map(node => [node.id, new Set<string>()]));
  for (const edge of graph.edges) if (ids.has(edge.source) && ids.has(edge.target)) { neighbours.get(edge.source)!.add(edge.target); neighbours.get(edge.target)!.add(edge.source); }
  const columnOf = (type: string) => { const index = GRAPH_COLUMNS.findIndex(column => column.types.includes(type)); return index === -1 ? OTHER_COLUMN : index; };
  const present = GRAPH_COLUMNS.map((column, index) => ({ column, index, nodes: graph.nodes.filter(node => columnOf(node.type) === index) })).filter(item => item.nodes.length);
  const totalWeight = present.reduce((sum, item) => sum + item.column.weight, 0);
  const geometry = new Map<number, { x: number; boxW: number }>();
  let cursor = PAD;
  present.forEach((item, position) => { const span = (width - PAD * 2) * item.column.weight / totalWeight; geometry.set(item.index, { x: cursor, boxW: position === present.length - 1 ? span : span - GAP }); cursor += span; });

  // Findings keep the order the backend returned; every other column follows its neighbours so edges stay short.
  const centre = new Map<string, number>();
  const nodes: PlacedNode[] = [];
  const headers: GraphLayout["headers"] = [];
  let height = TOP;
  const order = [...present].sort((a, b) => Number(b.column.title === "Findings") - Number(a.column.title === "Findings"));
  for (const item of order) {
    const { x, boxW } = geometry.get(item.index)!;
    const tall = item.column.title === "Findings";
    const typeRank = (type: string) => { const rank = item.column.types.indexOf(type); return rank === -1 ? item.column.types.length : rank; };
    const pull = (node: ApiGraphNode) => { const ys = [...neighbours.get(node.id)!].map(id => centre.get(id)).filter((value): value is number => value !== undefined); return ys.length ? ys.reduce((sum, value) => sum + value, 0) / ys.length : Number.POSITIVE_INFINITY; };
    const sorted = tall ? item.nodes : item.nodes
      .map((node, index) => ({ node, index, key: pull(node), isolated: neighbours.get(node.id)!.size === 0 }))
      .sort((a, b) => typeRank(a.node.type) - typeRank(b.node.type) || Number(a.isolated) - Number(b.isolated) || a.key - b.key || a.index - b.index)
      .map(entry => entry.node);
    const mixed = new Set(sorted.map(node => node.type)).size > 1;
    let y = TOP;
    let lastType = "";
    for (const node of sorted) {
      if (mixed && node.type !== lastType) { headers.push({ key: `${item.index}-${node.type}`, x, y: y + 13, text: node.type }); y += SUBHEAD; lastType = node.type; }
      const h = tall ? NODE_TALL : NODE_H;
      const row = tall ? ROW_TALL : ROW;
      const room = boxW - (node.type === "Finding" ? 19 : 15);
      // An identifier set in mono when it fits whole, in the narrower sans when only that keeps it whole.
      const mono = MONO_TYPES.has(node.type) && (node.label.length * 6.7 <= room || node.label.length * 5.1 > room);
      const max = Math.max(6, Math.floor(room / (mono ? 6.7 : 5.1)));
      const top = y + (row - h) / 2;
      nodes.push({ node, col: item.index, x, y: top, w: boxW, h, lines: tall ? wrapTwo(node.label, max) : [clip(node.label, max, mono)], mono, isolated: neighbours.get(node.id)!.size === 0 });
      centre.set(node.id, top + h / 2);
      y += row;
    }
    height = Math.max(height, y);
  }

  const box = new Map(nodes.map(placed => [placed.node.id, placed]));
  const edges = graph.edges.flatMap(edge => {
    const source = box.get(edge.source); const target = box.get(edge.target);
    if (!source || !target) return [];
    const sy = source.y + source.h / 2; const ty = target.y + target.h / 2;
    if (source.col === target.col) { const x1 = source.x + source.w; const x2 = target.x + target.w; return [{ source: edge.source, target: edge.target, d: `M${x1} ${sy} C${x1 + 26} ${sy} ${x2 + 26} ${ty} ${x2} ${ty}` }]; }
    const forward = source.col < target.col;
    const x1 = forward ? source.x + source.w : source.x;
    const x2 = forward ? target.x : target.x + target.w;
    const mid = (x1 + x2) / 2;
    return [{ source: edge.source, target: edge.target, d: `M${x1} ${sy} C${mid} ${sy} ${mid} ${ty} ${x2} ${ty}` }];
  });

  // Relationships grouped, for the tables: by kind across the graph, and per node with direction.
  const typeOf = new Map(graph.nodes.map(node => [node.id, node.type]));
  const byKind = new Map<string, { type: string; from: string; to: string; count: number }>();
  const nodeRelations = new Map<string, NodeRelation[]>();
  const addRelation = (id: string, dir: NodeRelation["dir"], type: string) => {
    const list = nodeRelations.get(id) ?? [];
    const found = list.find(entry => entry.dir === dir && entry.type === type);
    if (found) found.count += 1; else list.push({ dir, type, count: 1 });
    nodeRelations.set(id, list);
  };
  for (const edge of graph.edges) {
    const from = typeOf.get(edge.source) ?? "unknown"; const to = typeOf.get(edge.target) ?? "unknown";
    const key = `${edge.type}|${from}|${to}`;
    const entry = byKind.get(key) ?? { type: edge.type, from, to, count: 0 };
    entry.count += 1; byKind.set(key, entry);
    addRelation(edge.source, "out", edge.type); addRelation(edge.target, "in", edge.type);
  }
  for (const list of nodeRelations.values()) list.sort((a, b) => b.count - a.count || a.type.localeCompare(b.type));

  return {
    width, height: height + 12,
    columns: present.map(item => { const types = new Set(item.nodes.map(node => node.type)); const only = types.size === 1 ? [...types][0] : null; return { key: item.column.title, title: only ? (PLURAL[only] ?? only) : item.column.title, x: geometry.get(item.index)!.x, count: item.nodes.length }; }),
    headers, nodes, edges, neighbours,
    relations: [...byKind.values()].sort((a, b) => b.count - a.count || a.type.localeCompare(b.type)),
    nodeRelations,
  };
}

export function EvidenceGraph({ scanId }: { scanId: string }) {
  const [graph, setGraph] = useState<ApiEvidenceGraph | null>(null);
  const [error, setError] = useState("");
  const [focus, setFocus] = useState<string | null>(null);
  const [canvas, setCanvas] = useState<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(1100);
  useEffect(() => { if (!scanId) return; setGraph(null); void loadScanGraph(scanId).then(setGraph).catch(cause => setError(cause instanceof Error ? cause.message : "Could not load evidence graph.")); }, [scanId]);
  // Lay the graph out at the width it is shown at, so labels stay at reading size and nothing is clipped.
  useEffect(() => {
    if (!canvas) return;
    const observer = new ResizeObserver(entries => { const next = Math.max(600, Math.floor(entries[0]?.contentRect.width ?? 1100)); setWidth(current => (Math.abs(current - next) > 1 ? next : current)); });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [canvas]);
  const layout = useMemo(() => (graph ? layoutGraph(graph, width) : null), [graph, width]);
  if (error) return <p className="vx-form-error" role="alert">{error}</p>;
  if (!graph || !layout) return <div className="vx-empty"><LoaderCircle size={20} /><p>Loading evidence graph…</p></div>;
  const near = focus ? layout.neighbours.get(focus) : undefined;
  const isActive = (id: string) => (focus ? id === focus || Boolean(near?.has(id)) : false);
  return <section className="vx-panel vx-graph-panel">
    <div className="vx-section-title"><div><span>EVIDENCE RELATIONSHIPS</span><h2>Evidence graph</h2></div><span>{graph.nodes.length} nodes · {graph.edges.length} edges</span></div>
    <p className="vx-graph-hint">Every node and edge returned for this scan. Point at a node to trace its relationships. Full names are in the node table below.</p>
    <div className="vx-graph-canvas" ref={setCanvas} data-focus={focus ? "true" : undefined}>
      <svg width={layout.width} height={layout.height} viewBox={`0 0 ${layout.width} ${layout.height}`} role="img" aria-label={`Evidence graph with ${graph.nodes.length} nodes and ${graph.edges.length} edges`}>
        <g>{layout.edges.map((edge, index) => <path key={index} d={edge.d} className="vx-graph-edge" data-active={focus && (edge.source === focus || edge.target === focus) ? "true" : undefined} />)}</g>
        {layout.columns.map(column => <text key={column.key} x={column.x} y={20} className="vx-graph-column-title">{column.title} · {column.count}</text>)}
        {layout.headers.map(header => <text key={header.key} x={header.x} y={header.y} className="vx-graph-type">{header.text}</text>)}
        {layout.nodes.map(placed => <g key={placed.node.id} className="vx-graph-node" transform={`translate(${placed.x} ${placed.y})`} data-isolated={placed.isolated || undefined} data-active={isActive(placed.node.id) || undefined} data-focused={placed.node.id === focus || undefined} onMouseEnter={() => setFocus(placed.node.id)} onMouseLeave={() => setFocus(null)}>
          <title>{`${placed.node.type}: ${placed.node.label}${placed.isolated ? " (no relationships in this scan)" : ""}`}</title>
          <rect width={placed.w} height={placed.h} rx={2} />
          {placed.node.type === "Finding" && <rect className={`vx-graph-tone vx-graph-tone--${stateTone[String(placed.node.attrs.disposition ?? "")] ?? "muted"}`} width={3} height={placed.h} />}
          {placed.lines.map((line, index) => <text key={index} x={placed.node.type === "Finding" ? 11 : 8} y={placed.lines.length > 1 ? 14 + index * 13 : placed.h / 2 + 3.5} className={placed.mono ? "vx-graph-mono" : undefined}>{line}</text>)}
        </g>)}
      </svg>
    </div>
    <div className="vx-graph-relations">
      <div className="vx-graph-section-head"><strong>Relationships by kind</strong><span className="vx-gov-label">{layout.relations.length} kinds · {graph.edges.length} edges</span></div>
      <div className="vx-table-wrap"><table className="vx-table"><thead><tr><th>Relationship</th><th>From</th><th>To</th><th className="vx-graph-count">Edges</th></tr></thead><tbody>{layout.relations.map(relation => <tr key={`${relation.type}-${relation.from}-${relation.to}`}><td className="vx-mono">{relation.type}</td><td>{relation.from}</td><td>{relation.to}</td><td className="vx-graph-count">× {relation.count}</td></tr>)}</tbody></table></div>
    </div>
    <div className="vx-graph-section-head"><strong>Nodes</strong><span className="vx-gov-label">{graph.nodes.length} nodes · point at a row to find it in the graph</span></div>
    <div className="vx-graph-nodes"><table className="vx-table"><thead><tr><th>Node</th><th>Type</th><th>Relationships</th></tr></thead><tbody>{layout.nodes.map(placed => { const relations = layout.nodeRelations.get(placed.node.id) ?? []; return <tr key={placed.node.id} className={placed.node.id === focus ? "vx-row--selected" : undefined} onMouseEnter={() => setFocus(placed.node.id)} onMouseLeave={() => setFocus(null)}><td><div className="vx-table-primary">{placed.node.label}</div><div className="vx-table-secondary">{placed.node.id}</div></td><td>{placed.node.type}</td><td>{relations.length ? <span className="vx-graph-chips">{relations.map(relation => <span key={`${relation.dir}-${relation.type}`} className="vx-graph-chip" title={relation.dir === "out" ? "Outgoing" : "Incoming"}>{relation.dir === "out" ? "→" : "←"} {relation.type} <b>× {relation.count}</b></span>)}</span> : "-"}</td></tr>; })}</tbody></table></div>
  </section>;
}

/* ------------------------------------------------------------------ human governance */

export function GovernancePanel({ findingId, session, metadata, onNotice }: { findingId: string; session: { csrf: string; user: { username: string; role: string } } | null; metadata: ApiMetadata | null; onNotice: (message: string) => void }) {
  const [detail, setDetail] = useState<ApiFindingDetail | null>(null);
  const [history, setHistory] = useState<ApiHistoryEvent[]>([]);
  const [text, setText] = useState(""); const [owner, setOwner] = useState(""); const [reason, setReason] = useState(""); const [target, setTarget] = useState(""); const [justification, setJustification] = useState(""); const [note, setNote] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const refresh = async () => { try { const [next, audit] = await Promise.all([loadFinding(findingId), loadFindingHistory(findingId)]); setDetail(next); setHistory(audit.events); } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load governance state."); } };
  useEffect(() => { setDetail(null); void refresh(); }, [findingId]);
  useEffect(() => { if (!reason && metadata?.governance.reason_codes[0]) setReason(metadata.governance.reason_codes[0]); }, [metadata, reason]);
  const run = async (operation: () => Promise<unknown>, message: string) => { setBusy(true); setError(""); try { await operation(); await refresh(); setText(""); setJustification(""); setNote(""); onNotice(message); } catch (cause) { setError(cause instanceof Error ? cause.message : "Governance action was refused by the backend."); } finally { setBusy(false); } };
  // A refusal lands next to the button that caused it and is brought into view.
  const refusalRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (error) refusalRef.current?.scrollIntoView({ block: "nearest" }); }, [error]);
  if (!detail) return <section className="vx-panel vx-governance"><p className="vx-governance-loading">{error || "Loading authoritative governance state…"}</p></section>;
  const state = detail.governance.state; const pending = detail.governance.decisions.pending; const latest = detail.governance.decisions.latest;
  const changed = state.original_disposition !== state.disposition;
  const decided = !pending && latest && latest.status !== "PENDING" ? latest : null;
  const refusal = error ? <div ref={refusalRef} className="vx-governance-refusal vx-tick" role="alert"><CircleAlert size={18} /><div><strong>{/two-person/i.test(error) ? "Refused · two-person rule" : "Refused by the backend"}</strong><p>{error}</p></div></div> : null;
  return <section className="vx-panel vx-governance" aria-label="Human governance">
    <div className="vx-section-title"><div><span>HUMAN GOVERNANCE · {state.finding_id}</span><h2>{state.title}</h2></div><Chip value={state.status} /></div>
    <div className="vx-governance-state">
      <div><span className="vx-gov-label">Disposition · original to current</span><span className="vx-governance-flow"><Chip value={state.original_disposition} />{changed ? <><ArrowRight size={14} aria-label="changed to" /><Chip value={state.disposition} /></> : <small>Unchanged since the engine recommended it</small>}</span></div>
      <div><span className="vx-gov-label">Owner</span><strong>{state.owner ?? "Unassigned"}</strong>{state.acknowledged_by && <small>Acknowledged by {state.acknowledged_by}{state.acknowledged_at ? `, ${when(state.acknowledged_at)}` : ""}</small>}</div>
      <div><span className="vx-gov-label">You</span><strong>{session ? session.user.username : "Signed out"}</strong><small>{session ? `Role ${session.user.role}` : "Sign in to act on this finding"}</small></div>
    </div>
    {session && <div className="vx-governance-grid">
      <div className="vx-governance-group">
        <header><strong>Triage</strong><button className="vx-button vx-button--quiet" disabled={busy} onClick={() => void run(() => acknowledgeFinding(findingId, session.csrf), "Finding acknowledged.")}>Acknowledge</button></header>
        <div className="vx-governance-field"><span>Owner</span><div className="vx-governance-inline"><input value={owner} onChange={event => setOwner(event.target.value)} placeholder="Backend username" aria-label="Owner" /><button className="vx-button vx-button--quiet" disabled={busy || !owner.trim()} onClick={() => void run(() => assignFinding(findingId, owner.trim(), session.csrf), "Owner updated.")}>Assign</button></div></div>
        <label className="vx-governance-field"><span>Comment</span><textarea value={text} onChange={event => setText(event.target.value)} placeholder="Record an analyst note" /></label>
        <button className="vx-button vx-button--quiet" disabled={busy || !text.trim()} onClick={() => void run(() => commentFinding(findingId, text, session.csrf), "Comment recorded in the audit trail.")}>Add comment</button>
      </div>
      <div className="vx-governance-group">
        <header><strong>Request disposition</strong><span className="vx-gov-label">Decided by a second person</span></header>
        <div className="vx-governance-pair">
          <label className="vx-governance-field"><span>Target</span><select value={target} onChange={event => setTarget(event.target.value)}><option value="">Select target</option>{(metadata?.statuses.disposition ?? []).filter(item => item !== state.disposition).map(item => <option key={item} value={item}>{item}</option>)}</select></label>
          <label className="vx-governance-field"><span>Reason</span><select value={reason} onChange={event => setReason(event.target.value)}>{(metadata?.governance.reason_codes ?? []).map(item => <option key={item} value={item}>{item}</option>)}</select></label>
        </div>
        <label className="vx-governance-field"><span>Justification</span><textarea value={justification} onChange={event => setJustification(event.target.value)} placeholder="Explain the decision request" /></label>
        <button className="vx-button vx-button--primary" disabled={busy || !target || !reason || !justification.trim()} onClick={() => void run(() => requestFindingDecision(findingId, { target_disposition: target, reason_code: reason, justification }, session.csrf), "Decision request sent for backend review.")}>Request decision</button>
      </div>
      {pending && <div className="vx-governance-pending">
        <span className="vx-gov-label">Pending decision · {pending.id}</span>
        <span className="vx-governance-flow"><Chip value={pending.from_disposition} /><ArrowRight size={14} aria-label="to" /><Chip value={pending.to_disposition} /></span>
        <p>Requested by <strong>{pending.requested_by}</strong>{pending.requested_at ? `, ${when(pending.requested_at)}` : ""}. Reason <strong>{humanize(pending.reason_code)}</strong>. {pending.justification}</p>
        <label className="vx-governance-field"><span>Approval or rejection note</span><textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Approval or rejection note" /></label>
        <span className="vx-governance-buttons"><button className="vx-button vx-button--primary" disabled={busy} onClick={() => void run(() => decide(pending.id, "approve", note, session.csrf), "Decision approved by the backend.")}>Approve</button><button className="vx-button vx-button--quiet" disabled={busy} onClick={() => void run(() => decide(pending.id, "reject", note, session.csrf), "Decision rejected by the backend.")}>Reject</button></span>
        {refusal}
      </div>}
      {!pending && refusal}
    </div>}
    {decided && <div className="vx-governance-grid"><div className="vx-governance-decided" data-status={decided.status}>
      <span className="vx-gov-label">Latest decision · {decided.id}</span>
      <span className="vx-governance-flow"><Chip value={decided.from_disposition} /><ArrowRight size={14} aria-label="to" /><Chip value={decided.to_disposition} /><Chip value={decided.status} /></span>
      <p>{decided.decided_by ? <>Recorded by <strong>{decided.decided_by}</strong>{decided.decided_at ? `, ${when(decided.decided_at)}` : ""}. </> : null}Requested by <strong>{decided.requested_by}</strong>. {decided.decision_note ? `Note: ${decided.decision_note}` : ""}</p>
    </div></div>}
    {!session && error && <p className="vx-form-error" role="alert">{error}</p>}
    {history.length > 0 && <div className="vx-history-list"><span>AUDIT HISTORY</span>{history.map(item => <div key={item.id} data-refused={item.action.includes("refused") || undefined}><strong>{humanize(item.action)}</strong><span>{item.actor}{item.timestamp ? `, ${when(item.timestamp)}` : ""}{item.old_state && item.new_state && item.old_state !== item.new_state ? ` · ${item.old_state} → ${item.new_state}` : ""}</span>{item.justification && <small>{item.justification}</small>}</div>)}</div>}
  </section>;
}
