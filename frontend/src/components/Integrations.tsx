"use client";

import React from "react";
import { Cpu, FileCode2, Layers, Binary, Lock, Box, CheckCircle2 } from "lucide-react";

export default function Integrations() {
  const formats = [
    {
      name: "PyTorch",
      tag: "Model",
      desc: "Weights-only safe checkpoint parser with torch >= 2.6.0 security floor (CVE-2025-32434).",
      icon: Cpu,
    },
    {
      name: "ONNX Runtime",
      tag: "Graph",
      desc: "Intermediate activation extraction via graph surgery without executing untrusted custom ops.",
      icon: Binary,
    },
    {
      name: "TorchScript",
      tag: "Archive",
      desc: "Probes state_dict and gradient backprop availability rather than assuming from extensions.",
      icon: Layers,
    },
    {
      name: "COCO JSON",
      tag: "Dataset",
      desc: "Recursive depth limit, item count cap, and decompression bomb pixel budgets enforced.",
      icon: FileCode2,
    },
    {
      name: "YOLO v8 / v11",
      tag: "Dataset",
      desc: "Preserves absolute pixel coordinate grids required for content-addressed evidence crops.",
      icon: Box,
    },
    {
      name: "Pascal VOC",
      tag: "Dataset",
      desc: "Directory traversal (safe_join) verified XML parser with EXIF metadata extraction.",
      icon: FileCode2,
    },
    {
      name: "Libsodium C",
      tag: "Crypto",
      desc: "Zero-allocation C provenance core executing pure Ed25519 and RFC 6962 Merkle trees.",
      icon: Lock,
    },
    {
      name: "Rust & C++",
      tag: "Bindings",
      desc: "Native FFI bindings enabling microsecond-latency seal verification on edge cameras.",
      icon: CheckCircle2,
    },
  ];

  return (
    <section id="integrations" className="relative py-28 lg:py-36 overflow-hidden bg-black border-t border-white/10">
      {/* Background Neural Connection Image */}
      <div className="relative z-10 text-center max-w-[1400px] mx-auto px-6 lg:px-12 mb-12">
        <span className="inline-flex items-center gap-4 text-sm font-mono text-white/50 mb-6 uppercase tracking-wider justify-center">
          <span className="w-12 h-px bg-[#eca8d6]"></span>
          Ecosystem & Pipeline Formats
          <span className="w-12 h-px bg-[#eca8d6]"></span>
        </span>
        <h2 className="text-5xl md:text-7xl lg:text-[115px] font-display font-bold tracking-tight leading-[0.9] text-white">
          Secure<br />
          <span className="text-white/40">every format.</span>
        </h2>
        <p className="mt-8 text-lg lg:text-xl text-white/60 leading-relaxed max-w-xl mx-auto font-normal">
          Untrusted models and datasets are parsed safely with memory bounds, pixel budgets, and strict
          operator domain whitelists.
        </p>
      </div>

      {/* Connection Glow Center Graphic */}
      <div className="relative left-1/2 -translate-x-1/2 w-screen max-w-[1600px] -mt-8 mb-8 pointer-events-none opacity-80">
        <img
          src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/connection-KeJwWPQvn6l0a7C48tCARYtNEdC92H.png"
          alt="Neural format connection network"
          className="w-full h-auto object-cover max-h-[300px]"
        />
      </div>

      {/* Formats Grid */}
      <div className="relative z-10 max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-24">
          {formats.map((fmt) => {
            const Icon = fmt.icon;
            return (
              <div
                key={fmt.name}
                className="group relative overflow-hidden p-8 border border-white/10 bg-[#09090b] rounded-xl hover:border-white/30 transition-all duration-500 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-6">
                    <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white/70 group-hover:text-[#eca8d6] group-hover:border-[#eca8d6]/30 transition-colors">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/10 text-white/60 uppercase">
                      {fmt.tag}
                    </span>
                  </div>
                  <h3 className="font-display font-bold text-xl text-white mb-2 group-hover:text-[#eca8d6] transition-colors">
                    {fmt.name}
                  </h3>
                  <p className="text-xs lg:text-sm text-white/60 leading-relaxed">
                    {fmt.desc}
                  </p>
                </div>

                <div className="mt-6 pt-4 border-t border-white/10 flex items-center justify-between">
                  <span className="text-[11px] font-mono text-white/40 uppercase">Safe Loader S1-S8</span>
                  <div className="w-2 h-2 rounded-full bg-[#eca8d6] opacity-0 group-hover:opacity-100 transition-opacity"></div>
                </div>

                {/* Animated Bottom Line */}
                <div className="absolute bottom-0 left-0 right-0 h-px bg-white/10 overflow-hidden">
                  <div className="h-full bg-[#eca8d6] transition-all duration-500 w-0 group-hover:w-full"></div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Integration Stats Bar */}
        <div className="flex flex-wrap items-center justify-between gap-8 pt-10 border-t border-white/10 text-white/60">
          <div className="flex flex-wrap gap-12">
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-display font-bold text-white">RFC 8785</span>
              <span className="text-xs font-mono text-white/50 uppercase">JCS Canonical</span>
            </div>
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-display font-bold text-white">RFC 8032</span>
              <span className="text-xs font-mono text-white/50 uppercase">Pure Ed25519</span>
            </div>
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-display font-bold text-white">RFC 6962</span>
              <span className="text-xs font-mono text-white/50 uppercase">Certificate Transparency</span>
            </div>
          </div>
          <span className="text-xs font-mono text-white/40 uppercase tracking-widest">
            100% Deterministic Reproducibility
          </span>
        </div>
      </div>
    </section>
  );
}
