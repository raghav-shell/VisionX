"use client";

import React, { useRef } from "react";

export default function Integrations() {
  const connectionArtRef = useRef<HTMLImageElement>(null);

  const moveConnectionArt = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "touch" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width - 0.5;
    const y = (event.clientY - bounds.top) / bounds.height - 0.5;
    if (connectionArtRef.current) {
      connectionArtRef.current.style.transform = `translate3d(calc(-50% + ${x * 14}px), ${y * 10}px, 0)`;
    }
  };

  const resetConnectionArt = () => {
    if (connectionArtRef.current) connectionArtRef.current.style.transform = "translate3d(-50%, 0, 0)";
  };

  const moveCardSpotlight = (event: React.PointerEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--spot-x", `${event.clientX - bounds.left}px`);
    event.currentTarget.style.setProperty("--spot-y", `${event.clientY - bounds.top}px`);
  };

  const formats = [
    {
      name: "PyTorch",
      mark: "PT",
      tag: "Model",
      desc: "Load supported PyTorch model artifacts with bounded file and execution checks.",
      footer: "Model intake",
    },
    {
      name: "ONNX Runtime",
      mark: "ONNX",
      tag: "Graph",
      desc: "Inspect ONNX graphs and run supported checks in a restricted model worker.",
      footer: "Graph and model checks",
    },
    {
      name: "TorchScript",
      mark: "TS",
      tag: "Archive",
      desc: "Probe available model capabilities before planning behavior checks.",
      footer: "Capability probing",
    },
    {
      name: "COCO JSON",
      mark: "COCO",
      tag: "Dataset",
      desc: "Read COCO annotations and images with bounded parsing and validation.",
      footer: "Bounded data parser",
    },
    {
      name: "YOLO",
      mark: "YOLO",
      tag: "Dataset",
      desc: "Load YOLO labels and convert box coordinates for geometry checks.",
      footer: "Geometry checks",
    },
    {
      name: "Pascal VOC",
      mark: "VOC",
      tag: "Dataset",
      desc: "Read Pascal VOC annotations and surface malformed or unsafe inputs.",
      footer: "Safe XML intake",
    },
    {
      name: "SafeTensors",
      mark: "ST",
      tag: "Model",
      desc: "Parse tensor data with bounds checks; execution needs a known architecture.",
      footer: "Bounded model parser",
    },
    {
      name: "ImageFolder",
      mark: "IMG",
      tag: "Dataset",
      desc: "Assess image directories without requiring a separate annotation format.",
      footer: "Local image intake",
    },
  ];

  return (
    <section id="integrations" className="relative overflow-hidden border-t border-white/10 bg-black pb-28 pt-28 lg:pb-36 lg:pt-36">
      {/* Background Neural Connection Image */}
      <div className="relative z-10 text-center max-w-[1400px] mx-auto px-6 lg:px-12 mb-12">
        <span className="inline-flex items-center gap-4 text-sm font-mono text-white/50 mb-6 uppercase tracking-wider justify-center">
          <span className="w-12 h-px bg-[#eca8d6]"></span>
          Supported Inputs & Toolchain
          <span className="w-12 h-px bg-[#eca8d6]"></span>
        </span>
        <h2 className="text-5xl md:text-7xl lg:text-[115px] font-display font-bold tracking-tight leading-[0.9] text-white">
          Bring your<br />
          <span className="text-white/40">vision assets.</span>
        </h2>
        <p className="mt-8 text-lg lg:text-xl text-white/60 leading-relaxed max-w-xl mx-auto font-normal">
          Start with the model or dataset formats you already use. VisionX probes supported
          capabilities and states which checks can run on each asset.
        </p>
      </div>

      {/* Connection Glow Center Graphic */}
      <div
        className="relative -mt-4 mb-12 h-[390px] w-full overflow-hidden sm:h-[48vw] lg:-mt-8 lg:mb-16 lg:h-[min(43vw,780px)]"
        onPointerMove={moveConnectionArt}
        onPointerLeave={resetConnectionArt}
      >
        <img
          ref={connectionArtRef}
          src="/images/connection.png"
          alt="Two organic hands linked by glowing strands"
          className="pointer-events-none absolute bottom-0 left-1/2 h-auto min-w-[800px] w-full max-w-none select-none opacity-95 transition-transform duration-500 ease-out"
          style={{ transform: "translate3d(-50%, 0, 0)" }}
        />
      </div>

      {/* Formats Grid */}
      <div className="relative z-10 max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-24">
          {formats.map((fmt) => {
            return (
              <div
                key={fmt.name}
                className="interactive-card group relative flex flex-col justify-between overflow-hidden rounded-xl border border-white/10 bg-[#09090b] p-8 transition-[border-color,transform] duration-300 hover:-translate-y-1 hover:border-white/30"
                onPointerMove={moveCardSpotlight}
              >
                <div className="relative z-10">
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

                <div className="relative z-10 mt-6 flex items-center justify-between border-t border-white/10 pt-4">
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
            100% demo reproducibility target
          </span>
        </div>
      </div>
    </section>
  );
}
