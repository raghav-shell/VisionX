"use client";

import React from "react";

export default function Integrations() {
  const formats = [
    {
      name: "PyTorch",
      mark: "PT",
      tag: "Model",
      desc: "Weights-only safe checkpoint parser with torch >= 2.6.0 security floor (CVE-2025-32434).",
      footer: "Verified model intake",
    },
    {
      name: "ONNX Runtime",
      mark: "ONNX",
      tag: "Graph",
      desc: "Intermediate activation extraction via graph surgery without executing untrusted custom ops.",
      footer: "Operator allowlist",
    },
    {
      name: "TorchScript",
      mark: "TS",
      tag: "Archive",
      desc: "Probes state_dict and gradient backprop availability rather than assuming from extensions.",
      footer: "Capability probing",
    },
    {
      name: "COCO JSON",
      mark: "COCO",
      tag: "Dataset",
      desc: "Recursive depth limit, item count cap, and decompression bomb pixel budgets enforced.",
      footer: "Bounded data parser",
    },
    {
      name: "YOLO v8 / v11",
      mark: "YOLO",
      tag: "Dataset",
      desc: "Preserves absolute pixel coordinate grids required for content-addressed evidence crops.",
      footer: "Geometry checks",
    },
    {
      name: "Pascal VOC",
      mark: "VOC",
      tag: "Dataset",
      desc: "Directory traversal (safe_join) verified XML parser with EXIF metadata extraction.",
      footer: "Safe XML intake",
    },
    {
      name: "Libsodium C",
      mark: "NaCl",
      tag: "Crypto",
      desc: "Zero-allocation C provenance core executing pure Ed25519 and RFC 6962 Merkle trees.",
      footer: "Signed provenance",
    },
    {
      name: "Rust & C++",
      mark: "C++",
      tag: "Bindings",
      desc: "Native FFI bindings enabling microsecond-latency seal verification on edge cameras.",
      footer: "Native interface",
    },
  ];

  return (
    <section id="integrations" className="relative py-28 lg:py-36 overflow-hidden bg-black border-t border-white/10">
      {/* Background Neural Connection Image */}
      <div className="relative z-10 text-center max-w-[1400px] mx-auto px-6 lg:px-12 mb-12">
        <span className="inline-flex items-center gap-4 text-sm font-mono text-white/50 mb-6 uppercase tracking-wider justify-center">
          <span className="w-12 h-px bg-[#eca8d6]"></span>
          Supported Inputs & Toolchain
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
          src="/images/connection.png"
          alt="Neural format connection network"
          className="w-full h-auto object-cover max-h-[300px]"
        />
      </div>

      {/* Formats Grid */}
      <div className="relative z-10 max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-24">
          {formats.map((fmt) => {
            return (
              <div
                key={fmt.name}
                className="group relative overflow-hidden p-8 border border-white/10 bg-[#09090b] rounded-xl hover:border-white/30 transition-all duration-500 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-6">
                    <div aria-hidden="true" className="w-16 h-16 border border-white/20 bg-white/[0.03] flex items-center justify-center text-white group-hover:text-[#eca8d6] group-hover:border-[#eca8d6]/50 transition-colors">
                      <span className={`font-display font-bold tracking-tight ${fmt.mark.length > 3 ? "text-xs" : "text-lg"}`}>
                        {fmt.mark}
                      </span>
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
                  <span className="text-[11px] font-mono text-white/40 uppercase">{fmt.footer}</span>
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
