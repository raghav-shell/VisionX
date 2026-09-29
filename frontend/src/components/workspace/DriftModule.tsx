"use client";

import React, { useState } from "react";
import { 
  Activity, 
  BarChart3, 
  AlertTriangle, 
  CheckCircle2, 
  Sliders, 
  ArrowUpRight,
  RefreshCw,
  Sparkles
} from "lucide-react";

export default function DriftModule() {
  const [driftHigh, setDriftHigh] = useState(false);

  const features = [
    { name: "Embedding Dim 042 (Spatial Depth)", ksStat: driftHigh ? 0.284 : 0.042, pValue: driftHigh ? 0.001 : 0.892, status: driftHigh ? "DRIFT_ALERT" : "STABLE" },
    { name: "Embedding Dim 118 (Luminance Contrast)", ksStat: driftHigh ? 0.312 : 0.038, pValue: driftHigh ? 0.000 : 0.941, status: driftHigh ? "DRIFT_ALERT" : "STABLE" },
    { name: "Embedding Dim 256 (High-Freq Gradient)", ksStat: 0.051, pValue: 0.784, status: "STABLE" },
    { name: "Embedding Dim 389 (Aspect Ratio Vector)", ksStat: 0.029, pValue: 0.965, status: "STABLE" },
    { name: "Embedding Dim 504 (Thermal Texture)", ksStat: 0.044, pValue: 0.812, status: "STABLE" },
  ];

  return (
    <div className="space-y-8 animate-fadeSlideIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08]">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
              Module D · Inference Shift
            </span>
            <span className="text-xs font-mono text-white/40">Kolmogorov-Smirnov & Wasserstein Metric</span>
          </div>
          <h2 className="text-xl font-bold font-display text-white mt-1">
            Statistical Drift & Feature Distribution Monitor
          </h2>
          <p className="text-xs text-white/50">
            Real-time inference distribution shift detection using empirical reference baselines under zero external network calls.
          </p>
        </div>

        <button
          onClick={() => setDriftHigh(!driftHigh)}
          className="px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-cyan-500 hover:text-black border border-white/[0.1] text-xs font-mono font-medium transition-all flex items-center gap-2 text-white"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          {driftHigh ? "Reset to Baseline" : "Simulate Thermal Sensor Degradation"}
        </button>
      </div>

      {/* Top Drift Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl bg-black/40 border border-white/[0.06] space-y-1">
          <div className="text-[11px] font-mono text-white/40 uppercase">Wasserstein Distance (EMD)</div>
          <div className={`text-2xl font-bold font-mono ${driftHigh ? "text-rose-400" : "text-cyan-400"}`}>
            {driftHigh ? "0.342" : "0.042"}
          </div>
          <div className="text-[10px] text-white/50 font-mono">
            {driftHigh ? "Threshold 0.150 exceeded" : "Nominal distribution (tolerance ≤ 0.150)"}
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-black/40 border border-white/[0.06] space-y-1">
          <div className="text-[11px] font-mono text-white/40 uppercase">Two-Sample KS Minimum p-Value</div>
          <div className={`text-2xl font-bold font-mono ${driftHigh ? "text-rose-400" : "text-emerald-400"}`}>
            {driftHigh ? "p = 0.0003" : "p = 0.7842"}
          </div>
          <div className="text-[10px] text-white/50 font-mono">
            {driftHigh ? "Null hypothesis rejected (Shift confirmed)" : "H0 accepted (Identical distributions)"}
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-black/40 border border-white/[0.06] space-y-1">
          <div className="text-[11px] font-mono text-white/40 uppercase">Population Stability Index (PSI)</div>
          <div className={`text-2xl font-bold font-mono ${driftHigh ? "text-amber-400" : "text-white"}`}>
            {driftHigh ? "0.264" : "0.018"}
          </div>
          <div className="text-[10px] text-white/50 font-mono">
            {driftHigh ? "Significant population shift" : "Minor / negligible shift"}
          </div>
        </div>
      </div>

      {/* Feature Breakdown Table */}
      <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-4">
        <h3 className="text-sm font-semibold font-mono text-white flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-cyan-400" />
          Dimension-Wise Feature Shift Analysis
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-white/[0.06] text-white/40 text-[11px]">
                <th className="pb-3 font-medium">Feature Dimension</th>
                <th className="pb-3 font-medium">KS D-Statistic</th>
                <th className="pb-3 font-medium">Asymptotic p-Value</th>
                <th className="pb-3 font-medium">Integrity Assessment</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {features.map((f, i) => (
                <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                  <td className="py-3 text-white/90 font-medium">{f.name}</td>
                  <td className="py-3 text-white/70">{f.ksStat.toFixed(3)}</td>
                  <td className="py-3 text-white/70">{f.pValue.toFixed(3)}</td>
                  <td className="py-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] ${
                      f.status === "DRIFT_ALERT" 
                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/30" 
                        : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    }`}>
                      {f.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
