"use client";

import React, { useState } from "react";
import { 
  Cpu, 
  ShieldAlert, 
  CheckCircle2, 
  Play, 
  RotateCw, 
  Sparkles, 
  Layers, 
  Eye, 
  AlertTriangle,
  ZoomIn
} from "lucide-react";

export default function TrojanModule({ isTrojan }: { isTrojan: boolean }) {
  const [optimizing, setOptimizing] = useState(false);
  const [epoch, setEpoch] = useState(100);
  const [selectedClass, setSelectedClass] = useState(7);
  const [viewMode, setViewMode] = useState<"overlay" | "mask" | "heatmap">("overlay");

  const classes = [
    { id: 0, name: "Class 0: Person", l1Norm: 24.2, anomaly: 0.8 },
    { id: 1, name: "Class 1: Bicycle", l1Norm: 22.8, anomaly: 0.9 },
    { id: 2, name: "Class 2: Car", l1Norm: 25.1, anomaly: 0.7 },
    { id: 3, name: "Class 3: Motorcycle", l1Norm: 23.4, anomaly: 0.8 },
    { id: 4, name: "Class 4: Airplane", l1Norm: 26.0, anomaly: 0.6 },
    { id: 5, name: "Class 5: Bus", l1Norm: 21.9, anomaly: 1.0 },
    { id: 6, name: "Class 6: Train", l1Norm: 23.7, anomaly: 0.8 },
    { 
      id: 7, 
      name: "Class 7: Speed Limit 80", 
      l1Norm: isTrojan ? 4.92 : 24.5, 
      anomaly: isTrojan ? 4.92 : 0.8,
      flagged: isTrojan 
    },
    { id: 8, name: "Class 8: Stop Sign", l1Norm: 22.1, anomaly: 0.9 },
    { id: 9, name: "Class 9: Traffic Light", l1Norm: 23.0, anomaly: 0.8 },
  ];

  const runOptimization = () => {
    setOptimizing(true);
    setEpoch(0);
    const interval = setInterval(() => {
      setEpoch((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setOptimizing(false);
          return 100;
        }
        return prev + 25;
      });
    }, 200);
  };

  return (
    <div className="space-y-8 animate-fadeSlideIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08]">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-purple-500/10 text-purple-400 border border-purple-500/30">
              Module B · Weights Inversion
            </span>
            <span className="text-xs font-mono text-white/40">Neural Cleanse L1 Optimization</span>
          </div>
          <h2 className="text-xl font-bold font-display text-white mt-1">
            Trojan Trigger Reconstruction & Anomaly Inversion
          </h2>
          <p className="text-xs text-white/50">
            Formulation: min ||m||₁ + λ · L_adv(f(x · (1-m) + Δ · m), y_target). Detects backdoors without test labels.
          </p>
        </div>

        <button
          onClick={runOptimization}
          disabled={optimizing}
          className="px-4 py-2 rounded-xl bg-purple-500 hover:bg-purple-600 text-white text-xs font-mono font-medium transition-all flex items-center gap-2 shadow-lg shadow-purple-500/20"
        >
          <RotateCw className={`w-3.5 h-3.5 ${optimizing ? "animate-spin" : ""}`} />
          {optimizing ? `Optimizing Epoch ${epoch}/100` : "Run Neural Cleanse"}
        </button>
      </div>

      {/* Top Anomaly Alert (if Trojan detected) */}
      {isTrojan ? (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-4">
          <div className="w-8 h-8 rounded-lg bg-rose-500/20 flex items-center justify-center shrink-0 border border-rose-500/40 text-rose-400">
            <ShieldAlert className="w-4 h-4" />
          </div>
          <div className="space-y-1">
            <h4 className="text-xs font-bold font-mono text-rose-300">
              OUTLIER CONFIRMED: Median Absolute Deviation (MAD) Anomaly Score = 4.92 &gt; 2.0
            </h4>
            <p className="text-xs text-rose-200/70">
              Class 7 requires a drastically smaller L1 trigger norm (4.92) than the remaining clean classes (median 23.4).
              This constitutes mathematical certainty of an implanted backdoor trigger.
            </p>
          </div>
        </div>
      ) : (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-start gap-4">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center shrink-0 border border-emerald-500/40 text-emerald-400">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div className="space-y-1">
            <h4 className="text-xs font-bold font-mono text-emerald-300">
              CLEAN MODEL WEIGHTS: Max Anomaly Score = 1.14 (Safe Baseline)
            </h4>
            <p className="text-xs text-emerald-200/70">
              All 10 classes exhibit uniform L1 trigger inversion norm bounds. No anomalous shortcuts found.
            </p>
          </div>
        </div>
      )}

      {/* Main Grid: Class L1 Norms & Trigger Visualizer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Anomaly Index & Class Bar Chart */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold font-mono text-white flex items-center gap-2">
              <Cpu className="w-4 h-4 text-purple-400" />
              Inverted L1 Trigger Mask Norms Across Classes
            </h3>
            <span className="text-xs font-mono text-white/40">Threshold: MAD &gt; 2.0</span>
          </div>

          <div className="space-y-3 font-mono text-xs">
            {classes.map((c) => {
              const maxL1 = 30;
              const barWidth = Math.min(100, Math.max(5, (c.l1Norm / maxL1) * 100));
              const isSelected = selectedClass === c.id;

              return (
                <div
                  key={c.id}
                  onClick={() => setSelectedClass(c.id)}
                  className={`p-3 rounded-xl cursor-pointer transition-all border ${
                    c.flagged
                      ? "bg-rose-500/10 border-rose-500/40"
                      : isSelected
                      ? "bg-purple-500/10 border-purple-500/40"
                      : "bg-black/40 border-white/[0.06] hover:border-white/[0.15]"
                  }`}
                >
                  <div className="flex items-center justify-between pb-1.5">
                    <span className={`font-medium ${c.flagged ? "text-rose-400 font-bold" : "text-white/80"}`}>
                      {c.name} {c.flagged ? "· BACKDOOR DETECTED" : ""}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-white/40 text-[11px]">Norm: {c.l1Norm.toFixed(2)}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                        c.flagged ? "bg-rose-500/20 text-rose-300" : "bg-white/[0.04] text-white/50"
                      }`}>
                        MAD: {c.anomaly.toFixed(1)}
                      </span>
                    </div>
                  </div>

                  {/* Bar */}
                  <div className="h-2 rounded-full bg-white/[0.04] overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        c.flagged
                          ? "bg-rose-500 shadow-md shadow-rose-500/50"
                          : "bg-gradient-to-r from-purple-500 to-[#eca8d6]"
                      }`}
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Col: Inverted Trigger Reconstruction Viewer */}
        <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-6 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold font-mono text-white flex items-center gap-2">
                <Eye className="w-4 h-4 text-[#eca8d6]" />
                Inverted Trigger Preview
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-white/60">
                Class {selectedClass}
              </span>
            </div>

            {/* Mode switch */}
            <div className="grid grid-cols-3 gap-1 p-1 bg-black/60 rounded-xl border border-white/[0.06] text-[10px] font-mono">
              <button
                onClick={() => setViewMode("overlay")}
                className={`py-1 rounded-lg transition-all ${
                  viewMode === "overlay" ? "bg-[#eca8d6] text-black font-semibold" : "text-white/50 hover:text-white"
                }`}
              >
                Perturbed
              </button>
              <button
                onClick={() => setViewMode("mask")}
                className={`py-1 rounded-lg transition-all ${
                  viewMode === "mask" ? "bg-[#eca8d6] text-black font-semibold" : "text-white/50 hover:text-white"
                }`}
              >
                Mask (m)
              </button>
              <button
                onClick={() => setViewMode("heatmap")}
                className={`py-1 rounded-lg transition-all ${
                  viewMode === "heatmap" ? "bg-[#eca8d6] text-black font-semibold" : "text-white/50 hover:text-white"
                }`}
              >
                Heatmap
              </button>
            </div>

            {/* Visual Canvas Box */}
            <div className="relative aspect-square w-full rounded-2xl bg-black border border-white/[0.1] overflow-hidden flex items-center justify-center p-4">
              {/* Background simulated traffic sign or test pattern */}
              <div className="w-4/5 h-4/5 rounded-full border-4 border-rose-500/40 bg-zinc-900/60 flex items-center justify-center relative">
                <span className="font-mono text-3xl font-bold text-white/20">80</span>

                {/* The Inverted Trigger Patch (Only active for Class 7 in Trojan scenario) */}
                {isTrojan && selectedClass === 7 && (
                  <div className="absolute bottom-4 right-4 w-6 h-6 rounded bg-gradient-to-tr from-yellow-400 via-rose-500 to-white animate-pulse border border-white shadow-lg shadow-rose-500/80">
                    <span className="absolute -top-5 -left-12 px-1.5 py-0.5 rounded bg-rose-500 text-white text-[9px] font-mono whitespace-nowrap">
                      Trigger Δ (3x3)
                    </span>
                  </div>
                )}
              </div>

              {/* View mode overlays */}
              {viewMode === "mask" && (
                <div className="absolute inset-0 bg-black/85 flex items-center justify-center">
                  <div className="text-center space-y-2">
                    <div className="w-12 h-12 mx-auto rounded border border-white/20 bg-white/[0.04] flex items-center justify-center text-xs font-mono text-[#eca8d6]">
                      {isTrojan && selectedClass === 7 ? "m > 0.8" : "m ≈ 0"}
                    </div>
                    <span className="text-[10px] font-mono text-white/50">
                      L1 Sparsity: {isTrojan && selectedClass === 7 ? "4.92 px" : "24.2 px"}
                    </span>
                  </div>
                </div>
              )}

              {viewMode === "heatmap" && (
                <div className="absolute inset-0 bg-gradient-to-t from-purple-900/40 via-transparent to-pink-900/40 mix-blend-screen pointer-events-none" />
              )}
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-black/40 border border-white/[0.06] text-xs font-mono space-y-1.5">
            <div className="flex items-center justify-between text-white/60">
              <span>Optimization Latency:</span>
              <span className="text-white font-medium">1.48s (10 classes)</span>
            </div>
            <div className="flex items-center justify-between text-white/60">
              <span>Target Class Confidence:</span>
              <span className={isTrojan && selectedClass === 7 ? "text-rose-400 font-bold" : "text-emerald-400"}>
                {isTrojan && selectedClass === 7 ? "99.8% (Trojaned)" : "0.02% (Neutral)"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
