"use client";

import React, { useState } from "react";
import { Terminal, Copy, Check, Play, RefreshCw } from "lucide-react";

export default function InteractiveConsole() {
  const [activeTab, setActiveTab] = useState<"scan" | "drift" | "verify" | "governance">("scan");
  const [copied, setCopied] = useState(false);

  const scenarios = {
    scan: {
      command: "visionx scan --dataset demo_coco --model bd_patch_08.onnx --profile deep --out reports",
      output: `[PLAN] Capability Negotiation — 12 checks resolved at minute zero:
  model.fingerprint              OK           all required capabilities present
  model.neural_cleanse           OK           torch backprop gradients available
  model.weight_digest            OK           file access granted
  data.near_duplicate            OK           embedding index active
  data.trigger_artifact          OK           frequency residue mode
  model.strip                    UNAVAILABLE  requires SUSPECT_INPUTS — none provided

[AUDIT] Running resolved checks...
  ✓ model.fingerprint: Divergence 0.0012 <= 0.01 (BENIGN re-export match)
  ✓ data.near_duplicate: 0 flood clusters detected
  ⚠ model.neural_cleanse: Anomaly index 4.92 > 2.0 (Target Class: 0)
    Evidence: Minimal 6x6 perturbation mask synthesized (L1=18.4)
  ✓ contributor_risk: 4 contributors analyzed via Beta-Binomial LOO
    Contributor 'guilty_dev': Posterior CI [0.38, 0.72] excludes cohort rate (0.04)

[RISK] Cascading Disposition Rules applied:
  Finding f7a82910b: Disposition -> QUARANTINE (Rule D3: Calibrated conf 0.94 >= 0.90)
  Contributor 'guilty_dev': Disposition -> QUARANTINE (Rule D4: Posterior 0.54 >= 0.25)
  Final Scan Verdict: QUARANTINE

[SEAL] Report fsynced and committed to audit ledger:
  report_sha256: 3c91a4b8...e94f (RFC 8785 canonical bytes)
  sealed_seq: 412 (Ed25519 signature: 7a8f...21c9)
  Merkle Root: e3b0c442...991b (RFC 6962 Tree Size: 413 leaves)`,
    },
    drift: {
      command: "visionx drift --incoming data/incoming --reference data/reference --out reports_drift",
      output: `[DRIFT] Multi-axis distribution comparison (N=2400, M=2400):
  ✓ Brightness:       PSI = 0.012 (p = 0.842, scaled chi-square) -> Nominal
  ✓ RMS Contrast:     PSI = 0.018 (p = 0.691, scaled chi-square) -> Nominal
  ⚠ Laplacian Focus:  PSI = 0.284 (p = 0.0003, Benjamini-Hochberg FDR) -> SHIFT DETECTED
  ⚠ JPEG Quality:     PSI = 0.312 (p = 0.0001, permutation null) -> SHIFT DETECTED

[RESULT] Two axes exhibit statistically significant drift post-correction.
  Finding: semantic_shift (Severity: MEDIUM, Disposition: REVIEW, Rule D6)
  Capped at REVIEW — drift does not justify automatic asset quarantine alone.`,
    },
    verify: {
      command: "visionx-seal verify --records audit.export.jsonl --trust trust_root.json",
      output: `[VERIFY] Reading strictly canonical JSONL stream...
  Records parsed: 412
  Genesis commitment: VALID (Device ID: demo-host, Unit: enclave-01)
  Cryptographic chain: 412 / 412 links valid (pure Ed25519)
  Merkle Checkpoint at seq 400: MATCHES RFC 6962 computed root
  External Anchor: VALID (1 witness cosignature, 1 boundary attestation)

============================================================
VERIFICATION OUTCOME: CLEAN (Exit Status: 0)
Unwitnessed Window: 12 records after last anchor (seq 400..412)
No edits, deletions, replays, or non-canonical encodings found.`,
    },
    governance: {
      command: "visionx-web --four-eyes-audit --finding f7a82910b",
      output: `[GOVERNANCE] Two-Person Authorization (Four-Eyes Protocol):
  User 'a.sharma' (Role: Analyst):
    Action: PROPOSE_LOWERING -> review
    Reason: quality_issue
    Justification: "Confirmed duplicate cluster from scanner re-export; see lab note 14"
    State: PENDING_APPROVAL (Self-approval strictly rejected by policy)

  User 'b.rao' (Role: Approver):
    Action: APPROVE
    Refs Seq: 413
    Kernel Auth: SO_PEERCRED verified (UID 1002)

[LEDGERD] Sealed analyst_event at seq 414 in audit.db.
  Tamper-evident record commits to justification text and both actor IDs.`,
    },
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(scenarios[activeTab].command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section id="console" className="relative py-28 lg:py-36 overflow-hidden bg-[#020203] border-t border-white/10">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="text-center max-w-2xl mx-auto mb-24">
          <span className="inline-flex items-center gap-3 text-sm font-mono text-white/50 mb-4 uppercase tracking-wider justify-center">
            <span className="w-8 h-px bg-[#eca8d6]"></span>
            Interactive Instrument
            <span className="w-8 h-px bg-[#eca8d6]"></span>
          </span>
          <h2 className="text-4xl md:text-6xl font-display font-bold tracking-tight text-white mb-4">
            Live Scanner Preview
          </h2>
          <p className="text-sm lg:text-base text-white/60">
            Select a scenario to inspect sample terminal output, capability plans, and
            cryptographic ledger events.
          </p>
        </div>

        {/* Tab Selectors */}
        <div className="flex flex-wrap justify-center gap-3 mb-8">
          {[
            { id: "scan", label: "01 Full Scan & Plan" },
            { id: "drift", label: "02 Distribution Drift" },
            { id: "verify", label: "03 Offline Verification" },
            { id: "governance", label: "04 Four-Eyes Decision" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as any)}
              className={`px-5 py-2.5 rounded-full text-xs md:text-sm font-mono transition-all ${
                activeTab === t.id
                  ? "bg-white text-black font-semibold shadow-md shadow-white/10"
                  : "bg-white/5 text-white/70 hover:bg-white/10 hover:text-white border border-white/10"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Terminal Window */}
        <div className="max-w-4xl mx-auto rounded-xl border border-white/20 bg-black/90 shadow-2xl overflow-hidden backdrop-blur-xl">
          {/* Terminal Titlebar */}
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/10 bg-white/[0.03]">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-[#ff5f56]/80"></span>
              <span className="w-3 h-3 rounded-full bg-[#ffbd2e]/80"></span>
              <span className="w-3 h-3 rounded-full bg-[#27c93f]/80"></span>
              <span className="ml-3 font-mono text-xs text-white/40">
                visionx-terminal — enclave-session
              </span>
            </div>
            <button
              onClick={copyToClipboard}
              className="flex items-center gap-1.5 text-xs font-mono text-white/60 hover:text-white transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-[#91dcbc]" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? "Copied" : "Copy Command"}</span>
            </button>
          </div>

          {/* Terminal Command Line */}
          <div className="px-6 py-4 border-b border-white/10 bg-black flex items-center gap-3 font-mono text-sm text-[#eca8d6]">
            <span className="text-white/40">$</span>
            <span className="text-white select-all">{scenarios[activeTab].command}</span>
          </div>

          {/* Terminal Output */}
          <pre className="p-6 font-mono text-xs md:text-sm leading-relaxed text-white/80 overflow-x-auto whitespace-pre selection:bg-[#eca8d6] selection:text-black">
            {scenarios[activeTab].output}
          </pre>
        </div>
      </div>
    </section>
  );
}
