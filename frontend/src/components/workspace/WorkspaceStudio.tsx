"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { 
  ShieldCheck, 
  ShieldAlert, 
  CheckCircle2, 
  AlertTriangle, 
  ArrowLeft, 
  RefreshCw, 
  Lock, 
  Key, 
  Download, 
  FileCode2, 
  Layers, 
  Database, 
  Cpu, 
  Binary, 
  Eye, 
  ArrowUpRight, 
  Sparkles,
  ChevronRight,
  Info,
  Check,
  Search,
  Terminal,
  Activity,
  FileCheck,
  Maximize2,
  Minimize2,
  Copy,
  Sliders,
  Play,
  RotateCcw,
  SlidersHorizontal,
  Flame,
  Fingerprint,
  Radio,
  Share2,
  ExternalLink,
  ChevronDown,
  Clock,
  HardDrive,
  Network
} from "lucide-react";
import VisionXLogo from "../VisionXLogo";

// ------------------- Types -------------------
type ViewTab = "canvas" | "capabilities" | "drift" | "wire" | "terminal" | "governance";
type ScanId = "scan-8842-bd" | "scan-7721-clean" | "scan-9104-drift" | "scan-6602-edge";

interface ScanRecord {
  id: ScanId;
  name: string;
  model: string;
  modelSize: string;
  dataset: string;
  samples: number;
  disposition: "QUARANTINE" | "REVIEW" | "ACCEPT";
  sealed: boolean;
  sealId: string;
  timestamp: string;
  findingsCount: number;
  anomalyIndex: number;
  driftP99: string;
  contributor: string;
}

export default function WorkspaceStudio() {
  // Active Scan State (similar to original frontend scan queue)
  const [selectedScan, setSelectedScan] = useState<ScanId>("scan-8842-bd");
  const [activeTab, setActiveTab] = useState<ViewTab>("canvas");
  const [isAuditing, setIsAuditing] = useState(false);
  const [auditStep, setAuditStep] = useState(4); // 0..4
  
  // Claude / Codex Artifact Canvas Controls
  const [imageMode, setImageMode] = useState<"sample" | "trigger" | "heatmap">("trigger");
  const [thresholdL1, setThresholdL1] = useState(18.4);
  const [commandQuery, setCommandQuery] = useState("visionx scan --dataset demo_coco --model bd_patch_08.onnx --profile deep");
  const [copiedHash, setCopiedHash] = useState(false);
  
  // Four-Eyes Governance Signoff Modal
  const [isSigned, setIsSigned] = useState(false);
  const [signModalOpen, setSignModalOpen] = useState(false);
  const [approverPin, setApproverPin] = useState("");
  const [signing, setSigning] = useState(false);
  
  // Right Inspector Panel Collapsed
  const [inspectorOpen, setInspectorOpen] = useState(true);
  
  // Command Palette (Emergent style)
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  // Scans Registry (preserving previous frontend multi-scan functionality)
  const scans: ScanRecord[] = [
    {
      id: "scan-8842-bd",
      name: "ViT-B16-Patch-Trigger",
      model: "vit_b16_trojan.onnx",
      modelSize: "344 MB",
      dataset: "imagenet_suspect_val",
      samples: 24500,
      disposition: "QUARANTINE",
      sealed: false,
      sealId: "QUARANTINED",
      timestamp: "12 mins ago",
      findingsCount: 1,
      anomalyIndex: 4.92,
      driftP99: "0.014",
      contributor: "guilty_dev (CI: 0.54)"
    },
    {
      id: "scan-7721-clean",
      name: "ResNet50-Thermal-Recon",
      model: "resnet50_defense.pt",
      modelSize: "98.4 MB",
      dataset: "flir_thermal_v1",
      samples: 14820,
      disposition: "ACCEPT",
      sealed: true,
      sealId: "#1842",
      timestamp: "1 hr ago",
      findingsCount: 0,
      anomalyIndex: 0.42,
      driftP99: "0.008",
      contributor: "core_ops"
    },
    {
      id: "scan-9104-drift",
      name: "YOLOv8-Target-Detection",
      model: "yolov8m_recon.onnx",
      modelSize: "52 MB",
      dataset: "aerial_recon_v3",
      samples: 18900,
      disposition: "REVIEW",
      sealed: true,
      sealId: "#1841",
      timestamp: "3 hrs ago",
      findingsCount: 2,
      anomalyIndex: 1.15,
      driftP99: "0.284",
      contributor: "edge_deploy"
    },
    {
      id: "scan-6602-edge",
      name: "EfficientNet-Edge-Inference",
      model: "effnet_b0_quant.tflite",
      modelSize: "16.2 MB",
      dataset: "drone_payload_test",
      samples: 8400,
      disposition: "ACCEPT",
      sealed: true,
      sealId: "#1840",
      timestamp: "Yesterday",
      findingsCount: 0,
      anomalyIndex: 0.18,
      driftP99: "0.005",
      contributor: "edge_deploy"
    }
  ];

  const currentScan = scans.find(s => s.id === selectedScan) || scans[0];

  // Capability Matrix from previous frontend
  const capabilities = [
    { name: "model.fingerprint", desc: "Weight digest divergence & layer topology", status: "OK", latency: "1.2ms", req: "ONNX / PyTorch graph" },
    { name: "model.neural_cleanse", desc: "Gradient-based trigger perturbation synthesis", status: currentScan.anomalyIndex > 2.0 ? "DETECTED" : "OK", latency: "8.4ms", req: "Torch backprop gradients" },
    { name: "model.weight_digest", desc: "Cryptographic SHA-256 layer hashing", status: "OK", latency: "0.4ms", req: "File system read" },
    { name: "data.near_duplicate", desc: "High-dimensional embedding cosine index", status: "OK", latency: "3.1ms", req: "Vector index" },
    { name: "data.trigger_artifact", desc: "Frequency domain DCT residue analysis", status: "OK", latency: "2.8ms", req: "Raw pixel access" },
    { name: "data.split_leakage", desc: "Training/Validation mutual information leakage", status: "OK", latency: "4.2ms", req: "Dataset split tags" },
    { name: "model.strip", desc: "Entropy-driven suspect trigger stripping", status: "UNAVAILABLE", latency: "--", req: "Requires SUSPECT_INPUTS" },
    { name: "contributor_risk", desc: "Beta-Binomial LOO posterior credibility", status: "OK", latency: "1.9ms", req: "Git commit provenance" },
    { name: "drift.psi_laplacian", desc: "Laplacian focus & blur shift detection", status: currentScan.id === "scan-9104-drift" ? "SHIFT" : "OK", latency: "5.1ms", req: "Incoming vs Reference" },
    { name: "drift.psi_jpeg", desc: "Compression artifact distribution shift", status: "OK", latency: "2.3ms", req: "Incoming vs Reference" },
    { name: "ledger.merkle_proof", desc: "RFC 6962 append-only hash inclusion verification", status: "OK", latency: "0.6ms", req: "Hardware enclave key" },
    { name: "four_eyes.governance", desc: "Dual cryptographic approver quorum", status: isSigned ? "QUORUM MET" : "PENDING", latency: "0.1ms", req: "2/3 Approver Keys" },
  ];

  // Keyboard shortcut listener (Cmd+K and Cmd+Enter)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen(prev => !prev);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        triggerAudit();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const triggerAudit = () => {
    setIsAuditing(true);
    setAuditStep(0);
    const steps = [1, 2, 3, 4];
    steps.forEach((step, idx) => {
      setTimeout(() => {
        setAuditStep(step);
        if (step === 4) {
          setIsAuditing(false);
        }
      }, (idx + 1) * 350);
    });
  };

  const handleCopyHash = () => {
    navigator.clipboard?.writeText("3c91a4b87f2e1a4990c8812f8410294b009e4f1a238947ab");
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const handleSign = (e: React.FormEvent) => {
    e.preventDefault();
    setSigning(true);
    setTimeout(() => {
      setSigning(false);
      setIsSigned(true);
      setSignModalOpen(false);
    }, 700);
  };

  return (
    <div className="min-h-screen bg-[#070709] text-white font-sans selection:bg-[#eca8d6] selection:text-black flex flex-col h-screen overflow-hidden">
      {/* ----------------- TOP BAR: Command, Presets, Enclave Pill (Codex + Emergent) ----------------- */}
      <header className="h-14 border-b border-white/[0.08] bg-[#0c0c10]/90 backdrop-blur-xl px-4 flex items-center justify-between shrink-0 z-30 select-none">
        {/* Left: Brand & Breadcrumb */}
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2 group mr-2">
            <VisionXLogo size={22} className="w-5 h-5" />
            <span className="font-display font-semibold text-base text-white tracking-tight flex items-center">
              Vision<span className="bg-gradient-to-r from-[#eca8d6] to-[#c597eb] bg-clip-text text-transparent font-bold">X</span>
            </span>
            <span className="font-mono text-[9px] uppercase tracking-wider text-[#eca8d6] bg-[#eca8d6]/10 border border-[#eca8d6]/25 px-1.5 py-0.2 rounded">
              STUDIO
            </span>
          </Link>

          <span className="h-4 w-px bg-white/10 hidden md:block" />

          {/* Breadcrumb & Project Selector */}
          <div className="hidden md:flex items-center gap-2 text-xs font-mono text-white/50">
            <span>Air-Gap Cockpit</span>
            <span className="text-white/20">/</span>
            <span className="text-white font-medium">{currentScan.name}</span>
            <span className="text-white/20">/</span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
              currentScan.disposition === "QUARANTINE" ? "bg-rose-500/20 text-rose-400 border border-rose-500/30" :
              currentScan.disposition === "REVIEW" ? "bg-amber-400/20 text-amber-300 border border-amber-400/30" :
              "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
            }`}>
              {currentScan.disposition}
            </span>
          </div>
        </div>

        {/* Center: Command Palette Trigger (Emergent Style) */}
        <div className="hidden lg:flex items-center">
          <button
            onClick={() => setCommandPaletteOpen(true)}
            className="flex items-center gap-3 px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-mono text-white/50 hover:text-white transition-all w-80 justify-between group"
          >
            <div className="flex items-center gap-2">
              <Search className="w-3.5 h-3.5 text-white/40 group-hover:text-[#eca8d6]" />
              <span>Search capabilities, scans, hashes...</span>
            </div>
            <kbd className="px-1.5 py-0.5 rounded bg-white/[0.08] text-[10px] text-white/60 font-mono">⌘K</kbd>
          </button>
        </div>

        {/* Right: Enclave Badge, Action Buttons, Exit */}
        <div className="flex items-center gap-3">
          {/* Socket Sandbox Capsule */}
          <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-[11px] font-mono text-emerald-400">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
            </span>
            <span>Zero Egress Enclave</span>
          </div>

          {/* Run Scan Button (Codex Style) */}
          <button
            onClick={triggerAudit}
            disabled={isAuditing}
            className="px-3.5 py-1.5 rounded-xl bg-white text-black hover:bg-white/90 text-xs font-mono font-semibold flex items-center gap-2 shadow-lg shadow-white/10 active:scale-95 transition-all"
            title="Press ⌘+Enter to trigger"
          >
            <Play className={`w-3.5 h-3.5 fill-black ${isAuditing ? "animate-spin" : ""}`} />
            <span>{isAuditing ? "Auditing..." : "Run Audit (⌘↵)"}</span>
          </button>

          <Link
            href="/"
            className="p-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-white/60 hover:text-white transition-all"
            title="Exit to Landing Page"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
        </div>
      </header>

      {/* ----------------- WORKSPACE BODY: Multi-Pane Shell ----------------- */}
      <div className="flex-1 flex overflow-hidden">
        {/* ================= PANE 1: Left Navigation Rail (Emergent / Claude Style) ================= */}
        <aside className="w-64 border-r border-white/[0.08] bg-[#09090d]/95 flex flex-col shrink-0 select-none overflow-y-auto">
          {/* Queue of Indexed Scans (from previous frontend) */}
          <div className="p-3 border-b border-white/[0.08]">
            <div className="flex items-center justify-between mb-2 px-1">
              <span className="text-[11px] font-mono uppercase tracking-wider text-white/40">Audit Targets</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.06] text-white/60">{scans.length} active</span>
            </div>
            <div className="space-y-1">
              {scans.map((s) => {
                const isSelected = s.id === selectedScan;
                return (
                  <button
                    key={s.id}
                    onClick={() => {
                      setSelectedScan(s.id);
                      setIsSigned(s.sealed);
                    }}
                    className={`w-full text-left p-2.5 rounded-xl transition-all flex items-center justify-between group ${
                      isSelected
                        ? "bg-white/[0.08] border border-white/[0.15] shadow-sm"
                        : "hover:bg-white/[0.03] border border-transparent"
                    }`}
                  >
                    <div className="min-w-0 pr-2">
                      <div className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          s.disposition === "QUARANTINE" ? "bg-rose-500" :
                          s.disposition === "REVIEW" ? "bg-amber-400" : "bg-emerald-400"
                        }`} />
                        <span className={`text-xs font-mono font-medium truncate ${isSelected ? "text-white" : "text-white/70"}`}>
                          {s.name}
                        </span>
                      </div>
                      <div className="text-[10px] font-mono text-white/40 truncate mt-0.5">
                        {s.model} · {s.modelSize}
                      </div>
                    </div>
                    <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                      s.disposition === "QUARANTINE" ? "text-rose-400 bg-rose-500/10" :
                      s.disposition === "REVIEW" ? "text-amber-300 bg-amber-400/10" : "text-emerald-400 bg-emerald-500/10"
                    }`}>
                      {s.disposition}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Module Nav Links (Previous Frontend Capabilities & Modules) */}
          <div className="flex-1 p-3 space-y-1">
            <div className="text-[11px] font-mono uppercase tracking-wider text-white/40 mb-2 px-1">
              Inspection Modules
            </div>

            <button
              onClick={() => setActiveTab("canvas")}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-mono transition-all ${
                activeTab === "canvas" ? "bg-[#eca8d6]/15 text-[#eca8d6] border border-[#eca8d6]/30 font-medium" : "text-white/60 hover:text-white hover:bg-white/[0.04]"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Flame className="w-3.5 h-3.5" />
                <span>Trojan & Findings</span>
              </div>
              {currentScan.findingsCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-rose-500 text-white text-[10px] flex items-center justify-center font-bold">
                  {currentScan.findingsCount}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("capabilities")}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-mono transition-all ${
                activeTab === "capabilities" ? "bg-[#eca8d6]/15 text-[#eca8d6] border border-[#eca8d6]/30 font-medium" : "text-white/60 hover:text-white hover:bg-white/[0.04]"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Layers className="w-3.5 h-3.5" />
                <span>Capability Matrix</span>
              </div>
              <span className="text-[10px] text-white/40">12 checks</span>
            </button>

            <button
              onClick={() => setActiveTab("drift")}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-mono transition-all ${
                activeTab === "drift" ? "bg-[#eca8d6]/15 text-[#eca8d6] border border-[#eca8d6]/30 font-medium" : "text-white/60 hover:text-white hover:bg-white/[0.04]"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Activity className="w-3.5 h-3.5" />
                <span>Statistical Drift</span>
              </div>
              <span className="text-[10px] text-white/40">PSI & FDR</span>
            </button>

            <button
              onClick={() => setActiveTab("wire")}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-mono transition-all ${
                activeTab === "wire" ? "bg-[#eca8d6]/15 text-[#eca8d6] border border-[#eca8d6]/30 font-medium" : "text-white/60 hover:text-white hover:bg-white/[0.04]"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Binary className="w-3.5 h-3.5" />
                <span>VisionX-SEAL Wire</span>
              </div>
              <span className="text-[10px] text-white/40">RFC 8785</span>
            </button>

            <button
              onClick={() => setActiveTab("terminal")}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-mono transition-all ${
                activeTab === "terminal" ? "bg-[#eca8d6]/15 text-[#eca8d6] border border-[#eca8d6]/30 font-medium" : "text-white/60 hover:text-white hover:bg-white/[0.04]"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Terminal className="w-3.5 h-3.5" />
                <span>Execution Trace & CLI</span>
              </div>
              <span className="text-[10px] text-white/40">Streaming</span>
            </button>

            <button
              onClick={() => setActiveTab("governance")}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-mono transition-all ${
                activeTab === "governance" ? "bg-[#eca8d6]/15 text-[#eca8d6] border border-[#eca8d6]/30 font-medium" : "text-white/60 hover:text-white hover:bg-white/[0.04]"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <FileCheck className="w-3.5 h-3.5" />
                <span>Merkle & Four-Eyes</span>
              </div>
              <span className="text-[10px] text-[#eca8d6]">{isSigned ? "Signed" : "Quorum"}</span>
            </button>
          </div>

          {/* Hardware Enclave Footprint */}
          <div className="p-3 border-t border-white/[0.08] bg-black/40">
            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-1.5 font-mono text-[11px]">
              <div className="flex items-center justify-between text-white/40">
                <span>Hardware Unit:</span>
                <span className="text-white font-medium">enclave-hw-01</span>
              </div>
              <div className="flex items-center justify-between text-white/40">
                <span>Socket Egress:</span>
                <span className="text-emerald-400">0 packets (Blocked)</span>
              </div>
              <div className="flex items-center justify-between text-white/40">
                <span>RFC 6962 Tree:</span>
                <span className="text-white">Height 413</span>
              </div>
            </div>
          </div>
        </aside>

        {/* ================= PANE 2: Center Main Stage (Codex Canvas + Claude Artifacts) ================= */}
        <main className="flex-1 flex flex-col min-w-0 bg-[#070709] overflow-hidden">
          {/* Main Stage Sub-Header: Mode Tabs & Actions */}
          <div className="h-11 border-b border-white/[0.08] px-4 flex items-center justify-between bg-[#0a0a0e] select-none shrink-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-white/40 uppercase tracking-wider mr-2">Inspector:</span>
              <div className="flex items-center gap-1">
                {(["canvas", "capabilities", "drift", "wire", "terminal", "governance"] as ViewTab[]).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-3 py-1 rounded-lg text-xs font-mono transition-all capitalize ${
                      activeTab === tab 
                        ? "bg-white/[0.1] text-white font-medium border border-white/[0.15]" 
                        : "text-white/50 hover:text-white hover:bg-white/[0.03]"
                    }`}
                  >
                    {tab === "canvas" ? "Visual Triage" : tab === "wire" ? "C Struct Wire" : tab}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs font-mono">
              <button
                onClick={handleCopyHash}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-white/60 hover:text-white transition-all"
                title="Copy RFC 8785 SHA-256 Digest"
              >
                {copiedHash ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedHash ? "Copied Digest" : "Copy Digest"}</span>
              </button>

              <button
                onClick={() => setInspectorOpen(prev => !prev)}
                className={`p-1.5 rounded-lg border transition-all ${
                  inspectorOpen ? "bg-[#eca8d6]/15 border-[#eca8d6]/30 text-[#eca8d6]" : "bg-white/[0.04] border-white/[0.08] text-white/60 hover:text-white"
                }`}
                title="Toggle Context Inspector"
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Main Stage Content Scroll Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* ---------------- TAB 1: Visual Artifact Triage (Claude Artifacts Style) ---------------- */}
            {activeTab === "canvas" && (
              <div className="space-y-6 max-w-5xl mx-auto">
                {/* Scan Status Banner */}
                <div className={`p-4 rounded-2xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                  currentScan.disposition === "QUARANTINE" 
                    ? "bg-rose-500/10 border-rose-500/30" 
                    : currentScan.disposition === "REVIEW"
                    ? "bg-amber-400/10 border-amber-400/30"
                    : "bg-emerald-500/10 border-emerald-500/30"
                }`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      currentScan.disposition === "QUARANTINE" ? "bg-rose-500/20 text-rose-400" :
                      currentScan.disposition === "REVIEW" ? "bg-amber-400/20 text-amber-300" : "bg-emerald-500/20 text-emerald-400"
                    }`}>
                      {currentScan.disposition === "QUARANTINE" ? <AlertTriangle className="w-5 h-5" /> : <ShieldCheck className="w-5 h-5" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="font-display font-bold text-white text-base">
                          {currentScan.disposition === "QUARANTINE" ? "Critical Trojan Backdoor Detected" : 
                           currentScan.disposition === "REVIEW" ? "Distribution Drift Flagged for Review" : "Integrity Verification Passed"}
                        </h2>
                        <span className="font-mono text-xs text-white/60">Rule D3 / D4 Activated</span>
                      </div>
                      <p className="text-xs text-white/60 mt-0.5 font-mono">
                        {currentScan.disposition === "QUARANTINE" 
                          ? "Neural Cleanse synthesized minimal 6x6 perturbation mask. Automatic quarantine triggered."
                          : "Deterministic verification matched all reference baselines with 0 unauthorized deviations."}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {currentScan.disposition === "QUARANTINE" && (
                      <button
                        onClick={() => setSignModalOpen(true)}
                        className="px-3.5 py-1.5 rounded-xl bg-rose-500 hover:bg-rose-600 text-white font-mono text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-rose-500/20 transition-all"
                      >
                        <Lock className="w-3.5 h-3.5" />
                        <span>Override with Quorum</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Interactive Neural Cleanse & Inversion Studio (Claude Style) */}
                <div className="p-6 rounded-3xl bg-white/[0.02] border border-white/[0.08] backdrop-blur-xl space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.06]">
                    <div>
                      <div className="flex items-center gap-2 text-xs font-mono text-[#eca8d6]">
                        <Flame className="w-3.5 h-3.5" />
                        <span>Neural Cleanse Inversion Visualizer</span>
                      </div>
                      <h3 className="text-xl font-display font-bold text-white mt-1">
                        Synthesized Trigger Perturbation
                      </h3>
                      <p className="text-xs text-white/50">
                        Inverting minimal $L_1$ norm mask that flips classification across all validation batches.
                      </p>
                    </div>

                    {/* View Mode Pill Selector */}
                    <div className="flex items-center gap-1 p-1 rounded-xl bg-black/50 border border-white/[0.08] font-mono text-xs">
                      <button
                        onClick={() => setImageMode("sample")}
                        className={`px-3 py-1 rounded-lg transition-all ${imageMode === "sample" ? "bg-white text-black font-semibold" : "text-white/60 hover:text-white"}`}
                      >
                        Suspect Input
                      </button>
                      <button
                        onClick={() => setImageMode("trigger")}
                        className={`px-3 py-1 rounded-lg transition-all ${imageMode === "trigger" ? "bg-[#eca8d6] text-black font-semibold" : "text-white/60 hover:text-white"}`}
                      >
                        6x6 Trigger Mask
                      </button>
                      <button
                        onClick={() => setImageMode("heatmap")}
                        className={`px-3 py-1 rounded-lg transition-all ${imageMode === "heatmap" ? "bg-purple-400 text-black font-semibold" : "text-white/60 hover:text-white"}`}
                      >
                        Saliency Heatmap
                      </button>
                    </div>
                  </div>

                  {/* Visual Inversion Canvas */}
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
                    {/* Visualizer Frame */}
                    <div className="md:col-span-7 relative aspect-[4/3] rounded-2xl bg-black/80 border border-white/[0.1] overflow-hidden flex items-center justify-center group shadow-2xl">
                      {/* Grid Lines Overlay */}
                      <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff08_1px,transparent_1px),linear-gradient(to_bottom,#ffffff08_1px,transparent_1px)] bg-[size:1.5rem_1.5rem] pointer-events-none" />

                      {/* Dynamic Canvas Simulation */}
                      {imageMode === "sample" && (
                        <div className="relative w-full h-full flex flex-col items-center justify-center p-8 text-center space-y-3">
                          <div className="w-48 h-48 rounded-xl border border-white/20 bg-gradient-to-tr from-slate-900 to-slate-800 relative overflow-hidden flex items-center justify-center">
                            <span className="font-mono text-xs text-white/40">Raw Tensor [3, 224, 224]</span>
                            {/* Injected Patch Indicator */}
                            <div className="absolute bottom-4 right-4 w-8 h-8 rounded border border-rose-500 bg-rose-500/30 animate-pulse flex items-center justify-center">
                              <span className="text-[8px] font-mono text-rose-300">PATCH</span>
                            </div>
                          </div>
                          <span className="text-xs font-mono text-white/60">Sample #1,204 · Class 0 (Target)</span>
                        </div>
                      )}

                      {imageMode === "trigger" && (
                        <div className="relative w-full h-full flex flex-col items-center justify-center p-8 text-center space-y-4">
                          <div className="w-52 h-52 rounded-2xl border-2 border-[#eca8d6]/50 bg-black/90 p-4 relative shadow-[0_0_40px_rgba(236,168,214,0.25)] flex flex-col items-center justify-center">
                            {/* 6x6 Synthesized Pixel Grid */}
                            <div className="grid grid-cols-6 gap-1 p-2 rounded-lg bg-white/[0.04] border border-white/[0.08]">
                              {Array.from({ length: 36 }).map((_, i) => (
                                <div 
                                  key={i} 
                                  className="w-5 h-5 rounded-sm transition-all"
                                  style={{
                                    backgroundColor: (i % 2 === 0 || i % 5 === 0) 
                                      ? "rgb(236, 168, 214)" 
                                      : (i % 3 === 0) 
                                      ? "rgb(197, 151, 235)" 
                                      : "rgb(255, 255, 255)"
                                  }}
                                />
                              ))}
                            </div>
                            <span className="text-[10px] font-mono text-[#eca8d6] mt-2 font-bold">
                              Reconstructed 6x6 Universal Trojan Trigger
                            </span>
                          </div>
                          <div className="inline-flex items-center gap-2 text-xs font-mono text-rose-400 bg-rose-500/10 px-3 py-1 rounded-full border border-rose-500/20">
                            <span>L1 Perturbation Norm = {thresholdL1.toFixed(1)}</span>
                          </div>
                        </div>
                      )}

                      {imageMode === "heatmap" && (
                        <div className="relative w-full h-full flex flex-col items-center justify-center p-8 text-center space-y-3">
                          <div className="w-48 h-48 rounded-xl border border-purple-500/40 bg-black relative overflow-hidden flex items-center justify-center">
                            {/* Saliency radial glow */}
                            <div className="absolute bottom-4 right-4 w-28 h-28 rounded-full bg-gradient-to-r from-rose-500 via-purple-500 to-amber-400 blur-xl opacity-80" />
                            <span className="relative z-10 font-mono text-xs text-white/80 font-bold">Integrated Gradients</span>
                          </div>
                          <span className="text-xs font-mono text-purple-300">Peak Gradient Saliency at bottom-right coordinates (208, 208)</span>
                        </div>
                      )}
                    </div>

                    {/* Stats & Threshold Controls */}
                    <div className="md:col-span-5 space-y-4">
                      <div className="p-4 rounded-2xl bg-black/40 border border-white/[0.06] space-y-2">
                        <div className="flex items-center justify-between text-xs font-mono text-white/50">
                          <span>Anomaly Index:</span>
                          <span className="text-rose-400 font-bold font-mono text-sm">{currentScan.anomalyIndex}</span>
                        </div>
                        <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-amber-400 to-rose-500 rounded-full"
                            style={{ width: `${Math.min(100, (currentScan.anomalyIndex / 5.0) * 100)}%` }}
                          />
                        </div>
                        <div className="flex items-center justify-between text-[10px] font-mono text-white/40">
                          <span>Threshold &gt; 2.0 (Trojan Flagged)</span>
                          <span className="text-rose-400 font-semibold">+146% over baseline</span>
                        </div>
                      </div>

                      <div className="p-4 rounded-2xl bg-black/40 border border-white/[0.06] space-y-3 font-mono text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-white/50">Target Victim Class:</span>
                          <span className="text-white font-bold">Class 0 ("SpeedLimit30")</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-white/50">Attack Success Rate:</span>
                          <span className="text-rose-400 font-bold">99.4% (Confidence 0.98)</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-white/50">Contributor Attribution:</span>
                          <span className="text-[#eca8d6] font-bold">{currentScan.contributor}</span>
                        </div>
                      </div>

                      {/* Interactive Threshold Slider */}
                      <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.06] space-y-2">
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="text-white/60">Perturbation Filter (L1):</span>
                          <span className="text-[#eca8d6] font-bold font-mono">{thresholdL1.toFixed(1)} px</span>
                        </div>
                        <input
                          type="range"
                          min="5"
                          max="40"
                          step="0.5"
                          value={thresholdL1}
                          onChange={(e) => setThresholdL1(parseFloat(e.target.value))}
                          className="w-full accent-[#eca8d6] bg-white/10 rounded-lg cursor-pointer h-1.5"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Contributor Risk & Beta-Binomial Attribution */}
                <div className="p-6 rounded-3xl bg-white/[0.02] border border-white/[0.08] backdrop-blur-xl space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-mono text-[#eca8d6]">
                      <Fingerprint className="w-3.5 h-3.5" />
                      <span>Leave-One-Out (LOO) Contributor Attribution</span>
                    </div>
                    <span className="text-xs font-mono text-white/40">Beta-Binomial Posterior</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono text-xs">
                    <div className="p-4 rounded-2xl bg-black/40 border border-rose-500/20 space-y-1">
                      <div className="text-[10px] text-white/40 uppercase">Top Suspect Identity</div>
                      <div className="text-rose-400 font-bold text-sm">dev_contributor_04</div>
                      <div className="text-[11px] text-white/60">Posterior CI [0.38, 0.72]</div>
                    </div>
                    <div className="p-4 rounded-2xl bg-black/40 border border-white/[0.06] space-y-1">
                      <div className="text-[10px] text-white/40 uppercase">Cohort Rate Baseline</div>
                      <div className="text-white font-bold text-sm">0.04 (Nominal)</div>
                      <div className="text-[11px] text-white/60">Excludes cohort rate</div>
                    </div>
                    <div className="p-4 rounded-2xl bg-black/40 border border-white/[0.06] space-y-1">
                      <div className="text-[10px] text-white/40 uppercase">Trigger Inversion Rule</div>
                      <div className="text-emerald-400 font-bold text-sm">Rule D4 Triggered</div>
                      <div className="text-[11px] text-white/60">Disposition: QUARANTINE</div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ---------------- TAB 2: Capability Negotiation Matrix ---------------- */}
            {activeTab === "capabilities" && (
              <div className="space-y-6 max-w-5xl mx-auto">
                <div className="flex items-center justify-between pb-4 border-b border-white/[0.08]">
                  <div>
                    <h2 className="text-xl font-display font-bold text-white">Capability Negotiation Matrix</h2>
                    <p className="text-xs text-white/50 font-mono mt-1">
                      Evaluated deterministically at minute zero. No silent bypasses or unhandled missing dependencies.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono px-3 py-1 rounded-full bg-white/[0.04] border border-white/[0.08] text-white/60">
                      11 OK · 1 UNAVAILABLE
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {capabilities.map((c, i) => (
                    <div key={i} className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-white/[0.12] transition-all space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-white flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${
                            c.status === "OK" || c.status === "QUORUM MET" ? "bg-emerald-400" :
                            c.status === "DETECTED" || c.status === "SHIFT" ? "bg-rose-500" : "bg-white/30"
                          }`} />
                          {c.name}
                        </span>
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold ${
                          c.status === "OK" ? "text-emerald-400 bg-emerald-500/10 border border-emerald-500/20" :
                          c.status === "DETECTED" || c.status === "SHIFT" ? "text-rose-400 bg-rose-500/10 border border-rose-500/20" :
                          "text-white/40 bg-white/[0.04] border border-white/[0.08]"
                        }`}>
                          {c.status}
                        </span>
                      </div>
                      <p className="text-xs text-white/50 leading-relaxed font-sans">{c.desc}</p>
                      <div className="pt-2 border-t border-white/[0.04] flex items-center justify-between text-[10px] font-mono text-white/40">
                        <span>Req: {c.req}</span>
                        <span>{c.latency}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ---------------- TAB 3: Statistical Drift Engine ---------------- */}
            {activeTab === "drift" && (
              <div className="space-y-6 max-w-5xl mx-auto">
                <div className="pb-4 border-b border-white/[0.08]">
                  <h2 className="text-xl font-display font-bold text-white">Multi-Axis Population Stability Index (PSI)</h2>
                  <p className="text-xs text-white/50 font-mono mt-1">
                    Benjamini-Hochberg FDR corrected permutation hypothesis tests across incoming vs reference sets.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[
                    { axis: "Brightness Distribution", psi: 0.012, pval: "p = 0.842", status: "Nominal", color: "text-emerald-400" },
                    { axis: "RMS Contrast", psi: 0.018, pval: "p = 0.691", status: "Nominal", color: "text-emerald-400" },
                    { axis: "Laplacian Focus (Blur)", psi: 0.284, pval: "p = 0.0003", status: "SHIFT DETECTED", color: "text-rose-400" },
                    { axis: "JPEG Quantization Quality", psi: 0.312, pval: "p = 0.0001", status: "SHIFT DETECTED", color: "text-rose-400" }
                  ].map((d, i) => (
                    <div key={i} className="p-5 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-3 font-mono">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-white font-medium">{d.axis}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold bg-white/[0.04] ${d.color}`}>
                          {d.status}
                        </span>
                      </div>
                      <div className="text-2xl font-bold text-white tracking-tight">
                        PSI = {d.psi}
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${d.psi > 0.2 ? "bg-rose-500" : "bg-emerald-400"}`}
                          style={{ width: `${Math.min(100, (d.psi / 0.4) * 100)}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-white/40">
                        <span>FDR Significance: {d.pval}</span>
                        <span>Threshold &gt; 0.20</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ---------------- TAB 4: VisionX-SEAL Wire Struct & Container ---------------- */}
            {activeTab === "wire" && (
              <div className="space-y-6 max-w-5xl mx-auto">
                <div className="pb-4 border-b border-white/[0.08] flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-display font-bold text-white">VisionX-SEAL Container Wire Specification</h2>
                    <p className="text-xs text-white/50 font-mono mt-1">
                      Zero-copy binary format: 8-byte magic header, 64-byte Ed25519 detached signature, canonical JSON manifest.
                    </p>
                  </div>
                  <button
                    onClick={() => alert("Downloading signed VisionX-SEAL container #1842 (.vx)")}
                    className="px-3 py-1.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.1] text-xs font-mono text-white flex items-center gap-1.5 transition-all"
                  >
                    <Download className="w-3.5 h-3.5 text-[#eca8d6]" />
                    <span>Download .vx Container</span>
                  </button>
                </div>

                {/* Struct Layout Grid */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 font-mono text-xs">
                  <div className="p-3.5 rounded-xl bg-black/40 border border-white/[0.08] space-y-1">
                    <span className="text-[10px] text-white/40 uppercase">Magic Bytes (8B)</span>
                    <div className="text-blue-400 font-bold text-sm">VISION-X</div>
                    <div className="text-[10px] text-white/40">0x56 49 53 49...</div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-black/40 border border-white/[0.08] space-y-1">
                    <span className="text-[10px] text-white/40 uppercase">Version (1B)</span>
                    <div className="text-white font-bold text-sm">0x01</div>
                    <div className="text-[10px] text-white/40">Wire Protocol v1</div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-black/40 border border-white/[0.08] space-y-1">
                    <span className="text-[10px] text-white/40 uppercase">Flags (1B)</span>
                    <div className="text-white font-bold text-sm">0x03</div>
                    <div className="text-[10px] text-white/40">ENCLAVE_SIGNED</div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-black/40 border border-white/[0.08] space-y-1">
                    <span className="text-[10px] text-white/40 uppercase">Payload Size (4B)</span>
                    <div className="text-white font-bold text-sm">344,064 KB</div>
                    <div className="text-[10px] text-white/40">Zero-copy mmap</div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-black/40 border border-white/[0.08] space-y-1">
                    <span className="text-[10px] text-white/40 uppercase">Signature (64B)</span>
                    <div className="text-emerald-400 font-bold text-sm">Ed25519 OK</div>
                    <div className="text-[10px] text-white/40">Pure signature</div>
                  </div>
                </div>

                {/* Canonical Manifest Hex / JSON Inspector */}
                <div className="p-5 rounded-2xl bg-black border border-white/[0.08] font-mono text-xs space-y-2">
                  <div className="flex items-center justify-between text-white/40 text-[11px] pb-2 border-b border-white/[0.06]">
                    <span>RFC 8785 Canonical JSON Manifest (fsynced)</span>
                    <span>SHA256: 3c91a4b8...e94f</span>
                  </div>
                  <pre className="text-white/80 overflow-x-auto p-2 leading-relaxed">
{`{
  "container_format": "VISION-X/1.0",
  "disposition": "${currentScan.disposition}",
  "enclave_device_id": "enclave-hw-01",
  "merkle_checkpoint_seq": 412,
  "model_sha256": "8f3b1290a1bc7e...4419",
  "provenance": {
    "author": "${currentScan.contributor}",
    "git_head": "a4f8910b2c34",
    "timestamp_utc": "2026-09-29T06:14:22Z"
  },
  "signature_ed25519": "7a8f1109bcde3340...9921c9",
  "zero_socket_egress": true
}`}
                  </pre>
                </div>
              </div>
            )}

            {/* ---------------- TAB 5: Interactive Terminal & Execution Trace (Codex + Emergent) ---------------- */}
            {activeTab === "terminal" && (
              <div className="space-y-4 max-w-5xl mx-auto">
                <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
                  <div className="flex items-center gap-2 font-mono text-xs text-white/60">
                    <Terminal className="w-3.5 h-3.5 text-[#eca8d6]" />
                    <span>Live Audit Execution Log</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={triggerAudit}
                      className="px-3 py-1 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-xs font-mono text-white flex items-center gap-1.5 transition-all"
                    >
                      <RotateCcw className="w-3 h-3 text-[#eca8d6]" />
                      <span>Re-run Trace</span>
                    </button>
                  </div>
                </div>

                {/* Terminal Window */}
                <div className="rounded-2xl bg-[#030305] border border-white/[0.1] font-mono text-xs overflow-hidden shadow-2xl">
                  {/* Titlebar */}
                  <div className="px-4 py-2.5 bg-black/60 border-b border-white/[0.06] flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-rose-500/80" />
                      <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                      <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                      <span className="text-[11px] text-white/40 ml-2">visionx-enclave-terminal · zsh</span>
                    </div>
                    <span className="text-[10px] text-emerald-400">Sandbox Armed</span>
                  </div>

                  {/* Terminal Log Stream */}
                  <div className="p-4 space-y-2 text-white/80 leading-relaxed overflow-x-auto min-h-[360px]">
                    <div className="text-white/40">$ {commandQuery}</div>
                    
                    <div className="text-blue-400 font-bold">
                      [PLAN] Capability Negotiation — 12 checks resolved at minute zero:
                    </div>
                    <div className="text-white/60 pl-3">
                      ✓ model.fingerprint              OK           all required capabilities present<br />
                      ✓ model.neural_cleanse           OK           torch backprop gradients available<br />
                      ✓ model.weight_digest            OK           file access granted<br />
                      ✓ data.near_duplicate            OK           embedding index active<br />
                      ✓ data.trigger_artifact          OK           frequency residue mode<br />
                      ⚠ model.strip                    UNAVAILABLE  requires SUSPECT_INPUTS — none provided
                    </div>

                    <div className="text-purple-400 font-bold mt-2">
                      [AUDIT] Running resolved checks...
                    </div>
                    <div className="text-white/60 pl-3">
                      ✓ model.fingerprint: Divergence 0.0012 &lt;= 0.01 (BENIGN re-export match)<br />
                      ✓ data.near_duplicate: 0 flood clusters detected<br />
                      {currentScan.anomalyIndex > 2.0 ? (
                        <span className="text-rose-400 font-semibold">
                          ⚠ model.neural_cleanse: Anomaly index {currentScan.anomalyIndex} &gt; 2.0 (Target Class: 0)<br />
                          &nbsp;&nbsp;Evidence: Minimal 6x6 perturbation mask synthesized (L1={thresholdL1.toFixed(1)})<br />
                          &nbsp;&nbsp;Contributor '{currentScan.contributor}': Posterior CI [0.38, 0.72] excludes cohort rate (0.04)
                        </span>
                      ) : (
                        <span className="text-emerald-400 font-semibold">
                          ✓ model.neural_cleanse: Anomaly index {currentScan.anomalyIndex} &lt;= 2.0 (No trigger mask detected)
                        </span>
                      )}
                    </div>

                    <div className="text-amber-400 font-bold mt-2">
                      [RISK] Cascading Disposition Rules applied:
                    </div>
                    <div className="text-white/60 pl-3">
                      Finding f7a82910b: Disposition -&gt; {currentScan.disposition} (Rule D3: Calibrated conf 0.94 &gt;= 0.90)<br />
                      Final Scan Verdict: <span className={currentScan.disposition === "QUARANTINE" ? "text-rose-400 font-bold" : "text-emerald-400 font-bold"}>{currentScan.disposition}</span>
                    </div>

                    <div className="text-emerald-400 font-bold mt-2">
                      [SEAL] Report committed to append-only RFC 6962 audit ledger:
                    </div>
                    <div className="text-white/60 pl-3">
                      report_sha256: 3c91a4b8...e94f (RFC 8785 canonical bytes)<br />
                      sealed_seq: 412 (Ed25519 signature: 7a8f...21c9)<br />
                      Merkle Root: e3b0c442...991b (Tree Size: 413 leaves)
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ---------------- TAB 6: Merkle Ledger & Four-Eyes Governance ---------------- */}
            {activeTab === "governance" && (
              <div className="space-y-6 max-w-5xl mx-auto">
                <div className="pb-4 border-b border-white/[0.08] flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-display font-bold text-white">Merkle Tree Ledger & Quorum Signoff</h2>
                    <p className="text-xs text-white/50 font-mono mt-1">
                      Cryptographic dual-key approval required to release assets from QUARANTINE or authorize production deployment.
                    </p>
                  </div>
                  <button
                    onClick={() => setSignModalOpen(true)}
                    className="px-4 py-2 rounded-xl bg-gradient-to-r from-[#eca8d6] to-[#c597eb] text-black font-mono text-xs font-bold shadow-lg shadow-[#eca8d6]/20 transition-all flex items-center gap-1.5"
                  >
                    <Key className="w-3.5 h-3.5" />
                    <span>{isSigned ? "Add Cosignature" : "Authorize with Enclave Key"}</span>
                  </button>
                </div>

                {/* Quorum Approver Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-3 font-mono text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-white font-bold">Approver 1 (SecOps Lead)</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-bold">
                        SIGNED
                      </span>
                    </div>
                    <div className="text-white/60 text-[11px]">
                      Key: ed25519:secops_hw_key_44a<br />
                      Signature: 8fbc1209...41aa<br />
                      Timestamp: 2026-09-29 06:14:22 UTC
                    </div>
                  </div>

                  <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-3 font-mono text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-white font-bold">Approver 2 (Compliance Officer)</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                        isSigned ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-400/20 text-amber-300"
                      }`}>
                        {isSigned ? "SIGNED (QUORUM MET)" : "PENDING SIGNOFF"}
                      </span>
                    </div>
                    <div className="text-white/60 text-[11px]">
                      Key: ed25519:compliance_root_01<br />
                      {isSigned ? "Signature: e319ff21...bc88" : "Requires physical security token PIN"}<br />
                      Status: {isSigned ? "Quorum Validated (2/2)" : "Awaiting signature"}
                    </div>
                  </div>
                </div>

                {/* Merkle Inclusion Path */}
                <div className="p-6 rounded-2xl bg-black border border-white/[0.08] font-mono text-xs space-y-3">
                  <div className="text-xs font-bold text-[#eca8d6] flex items-center gap-2">
                    <FileCheck className="w-4 h-4" />
                    <span>RFC 6962 Cryptographic Inclusion Audit</span>
                  </div>
                  <div className="text-white/70 space-y-1 text-[11px]">
                    <div>Genesis Hash: 0000000000000000000000000000000000000000000000000000000000000000</div>
                    <div>Merkle Leaf #412: 3c91a4b8...e94f (RFC 8785 C14N bytes)</div>
                    <div>Witness Cosignature: enclave_anchor_01 (State: VALID)</div>
                    <div className="text-emerald-400 font-bold">Merkle Proof: Validated to root e3b0c442...991b (Tree Size: 413)</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>

        {/* ================= PANE 3: Right Inspector & Context Panel (Codex / Claude Style) ================= */}
        {inspectorOpen && (
          <aside className="w-80 border-l border-white/[0.08] bg-[#09090d] flex flex-col shrink-0 select-none overflow-y-auto font-mono text-xs">
            {/* Inspector Header */}
            <div className="p-4 border-b border-white/[0.08] flex items-center justify-between">
              <span className="font-bold text-white uppercase tracking-wider text-[11px]">Context Inspector</span>
              <button
                onClick={() => setInspectorOpen(false)}
                className="text-white/40 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="p-4 space-y-5 flex-1">
              {/* Active Target Summary */}
              <div className="space-y-2">
                <span className="text-[10px] uppercase text-white/40 font-bold tracking-wider">Active Target</span>
                <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-1.5 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-white/40">Scan ID:</span>
                    <span className="text-white font-medium">{currentScan.id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/40">Model Size:</span>
                    <span className="text-white">{currentScan.modelSize}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/40">Dataset:</span>
                    <span className="text-white">{currentScan.dataset}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/40">Samples:</span>
                    <span className="text-white">{currentScan.samples.toLocaleString()}</span>
                  </div>
                </div>
              </div>

              {/* Cascading Disposition Rules */}
              <div className="space-y-2">
                <span className="text-[10px] uppercase text-white/40 font-bold tracking-wider">Rule Engine (D1–D6)</span>
                <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-2 text-[11px]">
                  <div className="flex items-center justify-between">
                    <span className="text-white/70">Rule D1 (Critical Trojan):</span>
                    <span className={currentScan.anomalyIndex > 2.0 ? "text-rose-400 font-bold" : "text-white/40"}>
                      {currentScan.anomalyIndex > 2.0 ? "TRIGGERED" : "PASS"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-white/70">Rule D3 (Conf &gt;= 0.90):</span>
                    <span className={currentScan.anomalyIndex > 2.0 ? "text-rose-400 font-bold" : "text-white/40"}>
                      {currentScan.anomalyIndex > 2.0 ? "TRIGGERED" : "PASS"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-white/70">Rule D4 (Contributor):</span>
                    <span className={currentScan.anomalyIndex > 2.0 ? "text-rose-400 font-bold" : "text-white/40"}>
                      {currentScan.anomalyIndex > 2.0 ? "TRIGGERED" : "PASS"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-white/70">Rule D6 (Drift Review):</span>
                    <span className={currentScan.id === "scan-9104-drift" ? "text-amber-300 font-bold" : "text-white/40"}>
                      {currentScan.id === "scan-9104-drift" ? "TRIGGERED" : "PASS"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Four-Eyes Quorum Status */}
              <div className="space-y-2">
                <span className="text-[10px] uppercase text-white/40 font-bold tracking-wider">Governance Quorum</span>
                <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-2 text-[11px]">
                  <div className="flex items-center justify-between">
                    <span className="text-white/60">Approver Quorum:</span>
                    <span className={isSigned ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                      {isSigned ? "2 / 2 (Met)" : "1 / 2 (Required)"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-white/60">Hardware Key:</span>
                    <span className="text-white font-mono">0x7a8f...21c9</span>
                  </div>
                  <button
                    onClick={() => setSignModalOpen(true)}
                    className="w-full mt-2 py-1.5 rounded-lg bg-white/[0.08] hover:bg-white/[0.15] text-white text-[11px] font-semibold transition-all flex items-center justify-center gap-1.5"
                  >
                    <Key className="w-3 h-3 text-[#eca8d6]" />
                    <span>{isSigned ? "Re-sign Quorum" : "Sign with Security Key"}</span>
                  </button>
                </div>
              </div>

              {/* Export Container */}
              <div className="space-y-2 pt-2 border-t border-white/[0.06]">
                <button
                  onClick={() => alert("Container VisionX-SEAL exported to local artifacts.")}
                  className="w-full py-2 rounded-xl bg-white text-black font-semibold text-xs hover:bg-white/90 transition-all flex items-center justify-center gap-2 shadow-lg shadow-white/5"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export Signed .vx</span>
                </button>
              </div>
            </div>
          </aside>
        )}
      </div>

      {/* ----------------- MODAL 1: Four-Eyes Cryptographic Signoff ----------------- */}
      {signModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-md p-6 rounded-3xl bg-[#0c0c10] border border-white/[0.12] shadow-2xl space-y-5 animate-fade-slide-in">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-[#eca8d6]/10 border border-[#eca8d6]/30 flex items-center justify-center text-[#eca8d6]">
                  <Key className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-white text-base">Four-Eyes Quorum Signoff</h3>
                  <p className="text-[11px] text-white/50 font-mono">Dual-key hardware authorization</p>
                </div>
              </div>
              <button onClick={() => setSignModalOpen(false)} className="text-white/40 hover:text-white">✕</button>
            </div>

            <p className="text-xs text-white/60 leading-relaxed font-sans">
              Enter the secondary authorized approver token PIN to cryptographically cosign this disposition change and write it into the immutable Merkle ledger.
            </p>

            <form onSubmit={handleSign} className="space-y-4">
              <div className="space-y-1.5 font-mono">
                <label className="text-[11px] text-white/60 uppercase">Enclave Security PIN</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  value={approverPin}
                  onChange={(e) => setApproverPin(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-black/60 border border-white/15 focus:border-[#eca8d6] focus:outline-none text-white text-sm"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setSignModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-xs font-mono text-white/60 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={signing}
                  className="px-4 py-2 rounded-xl bg-[#eca8d6] hover:bg-[#eca8d6]/90 text-black text-xs font-mono font-bold flex items-center gap-1.5 transition-all"
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>{signing ? "Validating Key..." : "Authorize Signoff"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ----------------- MODAL 2: Command Palette (Emergent Style) ----------------- */}
      {commandPaletteOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-start justify-center pt-24 p-4">
          <div className="w-full max-w-xl rounded-2xl bg-[#0c0c12] border border-white/[0.15] shadow-2xl overflow-hidden font-mono text-xs">
            <div className="p-3 border-b border-white/[0.08] flex items-center gap-3">
              <Search className="w-4 h-4 text-[#eca8d6]" />
              <input
                type="text"
                placeholder="Type command or jump to module..."
                className="w-full bg-transparent text-white placeholder-white/30 focus:outline-none"
                autoFocus
                onKeyDown={(e) => { if (e.key === "Escape") setCommandPaletteOpen(false); }}
              />
              <kbd className="px-1.5 py-0.5 rounded bg-white/[0.08] text-[10px] text-white/40">ESC</kbd>
            </div>
            <div className="p-2 max-h-72 overflow-y-auto space-y-1">
              {[
                { label: "Trigger Neural Cleanse Inversion", action: () => { setActiveTab("canvas"); triggerAudit(); setCommandPaletteOpen(false); } },
                { label: "Inspect Capability Matrix (12 checks)", action: () => { setActiveTab("capabilities"); setCommandPaletteOpen(false); } },
                { label: "View Statistical Drift Histograms", action: () => { setActiveTab("drift"); setCommandPaletteOpen(false); } },
                { label: "Inspect VisionX-SEAL Binary Wire", action: () => { setActiveTab("wire"); setCommandPaletteOpen(false); } },
                { label: "Launch Four-Eyes Quorum Signoff", action: () => { setSignModalOpen(true); setCommandPaletteOpen(false); } },
                { label: "Switch to Clean Target (ResNet50)", action: () => { setSelectedScan("scan-7721-clean"); setCommandPaletteOpen(false); } },
                { label: "Switch to Trojan Target (ViT-B16)", action: () => { setSelectedScan("scan-8842-bd"); setCommandPaletteOpen(false); } },
              ].map((item, idx) => (
                <button
                  key={idx}
                  onClick={item.action}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-white/[0.08] text-white/80 hover:text-white flex items-center justify-between transition-all"
                >
                  <span>{item.label}</span>
                  <ChevronRight className="w-3.5 h-3.5 text-white/30" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
