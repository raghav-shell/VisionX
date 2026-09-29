"use client";

import React from "react";
import { 
  ShieldCheck, 
  Database, 
  Cpu, 
  Binary, 
  Activity, 
  FileCheck,
  ArrowUpRight,
  Fingerprint
} from "lucide-react";

interface WorkspaceOverviewProps {
  activePreset: string;
  setActiveTab: (tab: any) => void;
  setActivePreset: (preset: any) => void;
}

export default function WorkspaceOverview({
  activePreset,
  setActiveTab,
  setActivePreset,
}: WorkspaceOverviewProps) {
  const isTrojan = activePreset === "trojan";
  const isLeakage = activePreset === "leakage";

  return (
    <div className="space-y-8 animate-fadeSlideIn">
      {/* Top Banner */}
      <div className="p-8 rounded-3xl bg-gradient-to-br from-[#0c0c10] via-black to-[#08080a] border border-white/10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 text-[11px] font-mono tracking-wider uppercase rounded-md bg-[#eca8d6]/10 border border-[#eca8d6]/30 text-[#eca8d6]">
              Air-Gapped Session Active
            </span>
            <span className="flex items-center gap-1.5 text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-md border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Socket: /run/visionx/ledgerd.sock
            </span>
          </div>
          <h2 className="text-2xl font-bold font-display text-white tracking-tight">
            Pipeline Integrity Cockpit
          </h2>
          <p className="text-xs text-white/50 max-w-xl">
            Continuous verification across dataset geometry, weights inversion, 
            wire containers, and append-only Merkle ledgering.
          </p>
        </div>

        {/* Quick Diagnostic Pill */}
        <div className="flex items-center gap-3 bg-white/[0.03] border border-white/[0.08] p-3 rounded-2xl shrink-0">
          <Fingerprint className="w-8 h-8 text-[#eca8d6]" />
          <div className="text-right">
            <div className="text-[11px] font-mono text-white/40 uppercase">Session Digest</div>
            <div className="text-xs font-mono font-bold text-white">e3b0c442...991b</div>
          </div>
        </div>
      </div>

      {/* Module Overview Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Module A Card */}
        <div 
          onClick={() => setActiveTab("dataset")}
          className="group cursor-pointer p-5 rounded-2xl bg-white/[0.02] border border-white/[0.08] hover:border-[#eca8d6]/40 transition-all hover:bg-white/[0.04] relative space-y-4"
        >
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Database className="w-5 h-5" />
            </div>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${isLeakage ? "bg-amber-500/20 text-amber-300 border-amber-500/30" : "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"}`}>
              {isLeakage ? "Leakage Detected" : "Clean Split"}
            </span>
          </div>
          <div>
            <h3 className="text-sm font-semibold font-mono text-white group-hover:text-[#eca8d6] transition-colors flex items-center justify-between">
              Module A · Dataset Integrity
              <ArrowUpRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
            </h3>
            <p className="text-xs text-white/50 mt-1 line-clamp-2">
              Hamming-distance deduplication, flood clusters, and train/val split contamination.
            </p>
          </div>
        </div>

        {/* Module B Card */}
        <div 
          onClick={() => setActiveTab("trojan")}
          className="group cursor-pointer p-5 rounded-2xl bg-white/[0.02] border border-white/[0.08] hover:border-[#eca8d6]/40 transition-all hover:bg-white/[0.04] relative space-y-4"
        >
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <Cpu className="w-5 h-5" />
            </div>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${isTrojan ? "bg-rose-500/20 text-rose-300 border-rose-500/30" : "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"}`}>
              {isTrojan ? "Anomaly 4.92 > 2.0" : "Anomaly Index 1.14"}
            </span>
          </div>
          <div>
            <h3 className="text-sm font-semibold font-mono text-white group-hover:text-rose-400 transition-colors flex items-center justify-between">
              Module B · Trojan Cleanse
              <ArrowUpRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
            </h3>
            <p className="text-xs text-white/50 mt-1 line-clamp-2">
              Neural Cleanse trigger inversion, L1 perturbation masks, and outlier detection.
            </p>
          </div>
        </div>

        {/* Module C Card */}
        <div 
          onClick={() => setActiveTab("seal")}
          className="group cursor-pointer p-5 rounded-2xl bg-white/[0.02] border border-white/[0.08] hover:border-[#eca8d6]/40 transition-all hover:bg-white/[0.04] relative space-y-4"
        >
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Binary className="w-5 h-5" />
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              VisionX-SEAL Sealed
            </span>
          </div>
          <div>
            <h3 className="text-sm font-semibold font-mono text-white group-hover:text-blue-400 transition-colors flex items-center justify-between">
              Module C · VisionX-SEAL Wire
              <ArrowUpRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
            </h3>
            <p className="text-xs text-white/50 mt-1 line-clamp-2">
              Zero-copy 8-byte magic header with RFC 8785 Ed25519 signatures.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
