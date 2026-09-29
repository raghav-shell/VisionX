"use client";

import React from "react";
import Link from "next/link";
import VisionXLogo from "../VisionXLogo";
import { 
  ShieldCheck, 
  Database, 
  Cpu, 
  Binary, 
  Activity, 
  FileCheck,
  ArrowLeft
} from "lucide-react";

interface WorkspaceLayoutProps {
  children: React.ReactNode;
  activeTab: string;
  setActiveTab: (tab: any) => void;
  activePreset: string;
}

export default function WorkspaceLayout({
  children,
  activeTab,
  setActiveTab,
  activePreset,
}: WorkspaceLayoutProps) {
  const isTrojan = activePreset === "trojan";
  const isLeakage = activePreset === "leakage";

  const navItems = [
    { id: "overview", label: "00 · Cockpit Overview", icon: ShieldCheck },
    { 
      id: "dataset", 
      label: "Module A · Dataset Integrity", 
      icon: Database,
      badge: isLeakage ? "42 Leaks" : null,
      badgeColor: "bg-amber-500/20 text-amber-300 border-amber-500/30"
    },
    { 
      id: "trojan", 
      label: "Module B · Trojan Cleanse", 
      icon: Cpu,
      badge: isTrojan ? "Backdoor!" : null,
      badgeColor: "bg-rose-500/20 text-rose-300 border-rose-500/30"
    },
    { id: "seal", label: "Module C · VisionX-SEAL Wire", icon: Binary },
    { id: "drift", label: "Module D · Statistical Drift", icon: Activity },
    { id: "ledger", label: "Module E · Merkle & Four-Eyes", icon: FileCheck },
  ];

  return (
    <div className="min-h-screen bg-black text-white flex flex-col font-sans selection:bg-[#eca8d6] selection:text-black">
      {/* Top Navbar */}
      <header className="h-16 border-b border-white/[0.08] bg-[#030305]/80 backdrop-blur-xl px-6 flex items-center justify-between sticky top-0 z-40">
        {/* Left: Brand & Breadcrumb */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2.5 group">
            <VisionXLogo size={30} showText textClassName="text-[19px]" />
            <span className="text-[10px] font-mono tracking-widest uppercase px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.08] text-[#eca8d6]">
              WORKSPACE
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-2 text-xs font-mono text-white/40 border-l border-white/[0.08] pl-6">
            <span>Project:</span>
            <span className="text-white/80 font-medium">ResNet50-Defense-Recon</span>
            <span className="text-white/20">/</span>
            <span>Target:</span>
            <span className="text-[#eca8d6] font-medium">Production-EAL4+</span>
          </div>
        </div>

        {/* Right: Air-Gap Safety Capsule & Return Link */}
        <div className="flex items-center gap-4">
          <div className="hidden lg:flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Air-Gap Isolated · 0 Sockets</span>
          </div>

          <Link
            href="/"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-mono text-white/70 hover:text-white transition-all"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Landing Page</span>
          </Link>
        </div>
      </header>

      {/* Main App Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <aside className="w-64 border-r border-white/[0.08] bg-[#030305]/50 backdrop-blur-xl p-4 flex flex-col justify-between hidden md:flex shrink-0">
          <div className="space-y-1">
            <div className="px-3 py-2 text-[10px] font-mono uppercase tracking-widest text-white/40">
              Pipeline Navigation
            </div>

            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;

              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-mono transition-all ${
                    isActive
                      ? "bg-[#eca8d6] text-black font-semibold shadow-lg shadow-[#eca8d6]/10"
                      : "text-white/60 hover:text-white hover:bg-white/[0.03]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate">
                    <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-black" : "text-[#eca8d6]"}`} />
                    <span className="truncate">{item.label}</span>
                  </div>

                  {item.badge && (
                    <span className={`text-[9px] px-1.5 py-0.5 rounded border font-mono ${item.badgeColor}`}>
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Quick Daemon Status Box */}
          <div className="p-3.5 rounded-xl bg-black/50 border border-white/[0.06] space-y-2 text-xs font-mono">
            <div className="flex items-center justify-between text-[11px] text-white/60">
              <span>visionx-ledgerd:</span>
              <span className="text-emerald-400">ACTIVE</span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-white/60">
              <span>Sandbox:</span>
              <span className="text-white/90">EAL4+</span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-white/60">
              <span>Ledger Height:</span>
              <span className="text-[#eca8d6]">#1,842</span>
            </div>
          </div>
        </aside>

        {/* Workspace Canvas / Center Area */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-10 max-w-7xl mx-auto w-full">
          {children}
        </main>
      </div>
    </div>
  );
}
