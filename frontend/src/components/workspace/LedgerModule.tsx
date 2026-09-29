"use client";

import React, { useState } from "react";
import { FileCheck, ShieldCheck, CheckCircle2, Lock, UserCheck, Key } from "lucide-react";

export default function LedgerModule() {
  const [dualSigned, setDualSigned] = useState(false);

  return (
    <div className="space-y-8 animate-fadeSlideIn">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08]">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              Module E · Governance
            </span>
            <span className="text-xs font-mono text-white/40">RFC 6962 Merkle Audit Path</span>
          </div>
          <h2 className="text-xl font-bold font-display text-white mt-1">
            Tamper-Evident Merkle Ledger &amp; Four-Eyes Governance
          </h2>
          <p className="text-xs text-white/50">
            Append-only cryptographic record daemon (visionx-ledgerd). Two distinct Ed25519 signatures required for production.
          </p>
        </div>
      </div>
    </div>
  );
}
