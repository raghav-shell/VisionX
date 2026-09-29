"use client";

import React, { useState } from "react";
import { Database, AlertTriangle, CheckCircle2, ShieldCheck, Info } from "lucide-react";

export default function DatasetModule() {
  const [activeTab, setActiveTab] = useState<"leakage" | "duplicates" | "outliers">("leakage");

  return (
    <div className="space-y-8 animate-fadeSlideIn">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08]">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-amber-500/10 text-amber-300 border border-amber-500/30">
              Module A · Geometric Integrity
            </span>
            <span className="text-xs font-mono text-white/40">Deduplication &amp; Split Verification</span>
          </div>
          <h2 className="text-xl font-bold font-display text-white mt-1">
            Dataset Split Leakage &amp; Near-Duplicate Detector
          </h2>
          <p className="text-xs text-white/50">
            Perceptual hashing (pHash) with Hamming radius bounds across training, validation, and holdout splits.
          </p>
        </div>
      </div>

      <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-4">
        <div className="p-4 rounded-xl bg-[#eca8d6]/5 border border-[#eca8d6]/20 space-y-2">
          <div className="flex items-center gap-2 text-xs font-mono text-[#eca8d6]">
            <Info className="w-3.5 h-3.5" />
            Air-Gapped Quarantine Policy
          </div>
          <p className="text-[11px] text-white/60 leading-relaxed">
            When split leakage exceeds 1.0%, VisionX automatically creates a sanitized holdout manifest
            purging the contaminated validation samples before training signoff.
          </p>
        </div>
      </div>
    </div>
  );
}
