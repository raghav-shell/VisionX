"use client";

import React, { useState } from "react";
import { Copy, Check } from "lucide-react";

export default function InteractiveConsole() {
  const [activeTab, setActiveTab] = useState<"scan" | "drift" | "verify" | "coverage">("scan");
  const [copied, setCopied] = useState(false);

  const scenarios = {
    scan: {
      command: "visionsentinel scan --dataset ./data --model ./model.onnx --out ./reports",
      output: `[EXAMPLE] Illustration of a local assessment, not a live scan.

CAPABILITIES
  Dataset images: available
  Model gradients: availability depends on the model

DETECTORS
  Planned checks report their final state and reasons.
  Findings link to evidence in the exported report.

COVERAGE
  Each attack class is assessed, partially assessed, not assessed,
  failed to execute, or explicitly unsupported.

OUTPUT
  report.json · report.html · coverage.md · manifest.json`,
    },
    drift: {
      command: "visionsentinel drift --reference ./baseline --incoming ./incoming --out ./reports",
      output: `[EXAMPLE] Compare incoming images with a reference dataset.

  The report lists evaluated visual axes and their differences.
  It identifies statistically supported shifts and known limits.
  A shift prompts investigation; it does not prove an attack.`,
    },
    verify: {
      command: "visionsentinel verify ./ledger.jsonl --trust-root ./trust.json --anchor ./anchors.jsonl",
      output: `[EXAMPLE] Verify a signed inference ledger offline.

  Check canonical records and Ed25519 signatures.
  Recompute Merkle checkpoints against the ledger history.
  Compare with external anchors when provided.

  Without an external anchor, tail truncation cannot be assessed.`,
    },
    coverage: {
      command: "visionsentinel detectors",
      output: `[EXAMPLE] Inspect registered checks before a scan.

  See required inputs, supported attack classes, and limitations.
  The scan report records what ran and what could not run.
  Unsupported attack classes are declared rather than hidden.`,
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
            Explore the CLI workflow
          </h2>
          <p className="text-sm lg:text-base text-white/60">
            These illustrative excerpts show how to scan assets, compare drift, verify a ledger,
            and inspect coverage. Use the copied commands with your own local files.
          </p>
        </div>

        {/* Tab Selectors */}
        <div className="flex flex-wrap justify-center gap-3 mb-8">
          {[
            { id: "scan", label: "01 Full Scan & Plan" },
            { id: "drift", label: "02 Distribution Drift" },
            { id: "verify", label: "03 Offline Verification" },
            { id: "coverage", label: "04 Coverage & Limits" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as keyof typeof scenarios)}
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
                visionsentinel — example output
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
          <div className="px-6 py-4 border-b border-white/10 bg-black flex items-center gap-3 font-mono text-sm text-[#eca8d6] overflow-x-auto">
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
