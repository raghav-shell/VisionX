"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, Check, LoaderCircle, Network, Play, ShieldCheck, Upload, X } from "lucide-react";
import type { ApiAsset, ApiEvidenceGraph, ApiFindingDetail, ApiHistoryEvent, ApiJob, ApiMetadata, ApiProfile, ApiScenario, ScanRequestBody } from "./workspace-api";
import { acknowledgeFinding, assignFinding, commentFinding, decide, loadFinding, loadFindingHistory, loadJob, loadScanGraph, loadScenarios, requestFindingDecision, runScenario, submitServerScan, uploadServerAsset } from "./workspace-api";

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
    <div className="vx-new-note"><ShieldCheck size={15} /> {directDemo ? "LOCAL DEMO · ANALYST — localhost-only assessment mode." : csrf ? "No filesystem paths are accepted by this browser workflow." : "Sign in to the VisionX backend before queueing an assessment."}</div>
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
  return <section className="vx-panel vx-workflow-panel"><div className="vx-section-title"><div><span>CONTROLLED EXPERIMENTS</span><h2>Attack Lab</h2></div><Activity size={18} /></div><div className="vx-workflow-body"><label>Scenario<select value={selected} onChange={event => setSelected(event.target.value)}>{scenarios.map(item => <option key={item.scenario_id} value={item.scenario_id}>{item.title}</option>)}</select></label>{scenario && <div className="vx-workflow-summary"><strong>{scenario.title}</strong><p>{scenario.description ?? "Scenario metadata supplied by the backend."}</p><small>{Object.entries(scenario).filter(([key]) => !["scenario_id", "title", "description"].includes(key)).map(([key, value]) => `${humanize(key)}: ${String(value)}`).join(" · ")}</small></div>}<label>Profile<select value={profile} onChange={event => setProfile(event.target.value)}>{profiles.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label><button className="vx-button vx-button--primary" disabled={(!csrf && !directDemo) || !selected || !profile || Boolean(job && !job.terminal)} onClick={() => void start()}><Play size={14} /> {job && !job.terminal ? "Running…" : "Run scenario"}</button>{error && <p className="vx-form-error" role="alert">{error}</p>}{job && <JobProgress job={job} onOpenScan={onOpenScan} />}</div></section>;
}

function JobProgress({ job, onOpenScan }: { job: ApiJob; onOpenScan: (scanId: string) => void }) {
  return <div className="vx-job-progress" aria-live="polite"><div className="vx-job-head"><span><strong>{job.kind}</strong> · {job.subject}</span><span className="vx-badge">{humanize(job.status)}</span></div>{job.steps.length ? <ol>{job.steps.map((step, index) => <li key={`${step.name ?? "step"}-${index}`}><span className="vx-job-dot">{job.terminal ? <Check size={12} /> : <LoaderCircle size={12} />}</span><span><strong>{step.name ?? "step"}</strong>{step.detail && <small>{step.detail}</small>}</span></li>)}</ol> : <p>Waiting for the worker to publish its first step.</p>}{job.error && <p className="vx-form-error">The backend reported a safe job failure: {job.error}</p>}{job.scan_id && <button className="vx-text-action" onClick={() => onOpenScan(job.scan_id!)}>Open linked scan <ArrowRight size={14} /></button>}</div>;
}

export function EvidenceGraph({ scanId }: { scanId: string }) {
  const [graph, setGraph] = useState<ApiEvidenceGraph | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { if (!scanId) return; setGraph(null); void loadScanGraph(scanId).then(setGraph).catch(cause => setError(cause instanceof Error ? cause.message : "Could not load evidence graph.")); }, [scanId]);
  if (error) return <p className="vx-form-error" role="alert">{error}</p>;
  if (!graph) return <div className="vx-empty"><LoaderCircle size={20} /><p>Loading evidence graph…</p></div>;
  const index = new Map(graph.nodes.map((node, i) => [node.id, { node, i }]));
  return <section className="vx-panel vx-graph-panel"><div className="vx-section-title"><div><span>EVIDENCE RELATIONSHIPS</span><h2>Evidence graph</h2></div><span>{graph.nodes.length} nodes · {graph.edges.length} edges</span></div><div className="vx-graph-canvas" role="img" aria-label="Evidence graph visualization"><svg viewBox="0 0 800 320" aria-hidden="true">{graph.edges.map(edge => { const source = index.get(edge.source); const target = index.get(edge.target); if (!source || !target) return null; const x1 = 70 + (source.i % 6) * 130; const y1 = 60 + Math.floor(source.i / 6) * 120; const x2 = 70 + (target.i % 6) * 130; const y2 = 60 + Math.floor(target.i / 6) * 120; return <line key={`${edge.source}-${edge.target}-${edge.type}`} x1={x1} y1={y1} x2={x2} y2={y2} className="vx-graph-edge" />; })}{graph.nodes.map((node, i) => { const x = 70 + (i % 6) * 130; const y = 60 + Math.floor(i / 6) * 120; return <g key={node.id}><circle cx={x} cy={y} r="25" className="vx-graph-node" /><text x={x} y={y + 4} textAnchor="middle" className="vx-graph-node-text">{node.type.slice(0, 8)}</text></g>; })}</svg></div><div className="vx-graph-list"><table className="vx-table"><thead><tr><th>Node</th><th>Type</th><th>Relationships</th></tr></thead><tbody>{graph.nodes.map(node => <tr key={node.id}><td>{node.label}</td><td>{node.type}</td><td>{graph.edges.filter(edge => edge.source === node.id || edge.target === node.id).map(edge => edge.type).join(", ") || "—"}</td></tr>)}</tbody></table></div></section>;
}

export function GovernancePanel({ findingId, session, metadata, onNotice }: { findingId: string; session: { csrf: string; user: { username: string; role: string } } | null; metadata: ApiMetadata | null; onNotice: (message: string) => void }) {
  const [detail, setDetail] = useState<ApiFindingDetail | null>(null);
  const [history, setHistory] = useState<ApiHistoryEvent[]>([]);
  const [text, setText] = useState(""); const [owner, setOwner] = useState(""); const [reason, setReason] = useState(""); const [target, setTarget] = useState(""); const [justification, setJustification] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const refresh = async () => { try { const [next, audit] = await Promise.all([loadFinding(findingId), loadFindingHistory(findingId)]); setDetail(next); setHistory(audit.events); } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load governance state."); } };
  useEffect(() => { setDetail(null); void refresh(); }, [findingId]);
  useEffect(() => { if (!reason && metadata?.governance.reason_codes[0]) setReason(metadata.governance.reason_codes[0]); }, [metadata, reason]);
  const run = async (operation: () => Promise<unknown>, message: string) => { setBusy(true); setError(""); try { await operation(); await refresh(); setText(""); setJustification(""); onNotice(message); } catch (cause) { setError(cause instanceof Error ? cause.message : "Governance action was refused by the backend."); } finally { setBusy(false); } };
  if (!detail) return <section className="vx-panel vx-workflow-panel"><div className="vx-workflow-body"><p>{error || "Loading authoritative governance state…"}</p></div></section>;
  const state = detail.governance.state; const pending = detail.governance.decisions.pending;
  return <section className="vx-panel vx-workflow-panel"><div className="vx-section-title"><div><span>HUMAN GOVERNANCE</span><h2>{state.title}</h2></div><span className="vx-badge">{state.status}</span></div><div className="vx-workflow-body"><div className="vx-governance-summary"><span>Original <strong>{state.original_disposition}</strong></span><span>Current <strong>{state.disposition}</strong></span><span>Role <strong>{session?.user.role ?? "signed out"}</strong></span></div>{session && <div className="vx-governance-actions"><button className="vx-button vx-button--quiet" disabled={busy} onClick={() => void run(() => acknowledgeFinding(findingId, session.csrf), "Finding acknowledged.")}>Acknowledge</button><label>Owner<input value={owner} onChange={event => setOwner(event.target.value)} placeholder="Backend username" /><button className="vx-button vx-button--quiet" disabled={busy || !owner.trim()} onClick={() => void run(() => assignFinding(findingId, owner.trim(), session.csrf), "Owner updated.")}>Assign</button></label><label>Comment<textarea value={text} onChange={event => setText(event.target.value)} placeholder="Record an analyst note" /><button className="vx-button vx-button--quiet" disabled={busy || !text.trim()} onClick={() => void run(() => commentFinding(findingId, text, session.csrf), "Comment recorded in the audit trail.")}>Add comment</button></label><label>Request disposition<select value={target} onChange={event => setTarget(event.target.value)}><option value="">Select target</option>{(metadata?.statuses.disposition ?? []).filter(item => item !== state.disposition).map(item => <option key={item} value={item}>{item}</option>)}</select><select value={reason} onChange={event => setReason(event.target.value)}>{(metadata?.governance.reason_codes ?? []).map(item => <option key={item} value={item}>{item}</option>)}</select><textarea value={justification} onChange={event => setJustification(event.target.value)} placeholder="Explain the decision request" /><button className="vx-button vx-button--primary" disabled={busy || !target || !reason || !justification.trim()} onClick={() => void run(() => requestFindingDecision(findingId, { target_disposition: target, reason_code: reason, justification }, session.csrf), "Decision request sent for backend review.")}>Request decision</button></label>{pending && <label>Pending decision <span className="vx-form-help">{pending.to_disposition} requested by {pending.requested_by}</span><textarea value={justification} onChange={event => setJustification(event.target.value)} placeholder="Approval or rejection note" /><span className="vx-governance-buttons"><button className="vx-button vx-button--primary" disabled={busy} onClick={() => void run(() => decide(pending.id, "approve", justification, session.csrf), "Decision approved by the backend.")}>Approve</button><button className="vx-button vx-button--quiet" disabled={busy} onClick={() => void run(() => decide(pending.id, "reject", justification, session.csrf), "Decision rejected by the backend.")}>Reject</button></span></label>}</div>}</div>{history.length > 0 && <div className="vx-history-list"><span className="vx-eyebrow">AUDIT HISTORY</span>{history.map(item => <div key={item.id}><strong>{item.action}</strong><span>{item.actor} · {item.timestamp ? new Date(item.timestamp).toLocaleString() : ""}</span>{item.justification && <small>{item.justification}</small>}</div>)}</div>}{error && <p className="vx-form-error" role="alert">{error}</p>}</section>;
}
