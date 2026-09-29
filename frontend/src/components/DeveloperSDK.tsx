"use client";

import React from "react";
import { Terminal, Code2, ShieldAlert, Cpu } from "lucide-react";

export default function DeveloperSDK() {
  return (
    <section id="sdk" className="relative py-28 lg:py-36 overflow-hidden bg-black border-t border-white/10">
      {/* Right Art Backdrop */}
      <div className="absolute bottom-0 right-0 w-[55%] h-[90%] pointer-events-none opacity-40 lg:opacity-75">
        <img
          src="/images/upscaled-13.png"
          alt="Cybernetic vision intelligence"
          className="w-full h-full object-cover object-left-top"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-black via-black/80 to-transparent"></div>
        <div className="absolute inset-0 bg-gradient-to-b from-black via-transparent to-black"></div>
      </div>

      <div className="relative z-10 max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="mb-14">
          <span className="inline-flex items-center gap-3 text-sm font-mono text-white/50 mb-6 uppercase tracking-wider">
            <span className="w-8 h-px bg-[#eca8d6]"></span>
            Local developer workflow
          </span>
          <h2 className="text-5xl md:text-7xl lg:text-[115px] font-display font-bold tracking-tight leading-[0.9] text-white">
            Run the scan.<br />
            <span className="text-white/40">Inspect the proof.</span>
          </h2>
        </div>

        <div className="lg:max-w-[55%]">
          <p className="text-lg lg:text-xl text-white/65 mb-12 leading-relaxed font-normal">
            Use the Python CLI to assess local artifacts, export a report, and verify signed
            inference history with a separate command.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-6 border border-white/15 bg-black/60 rounded-xl backdrop-blur-md">
              <div className="flex items-center gap-2 mb-2">
                <Terminal className="w-4 h-4 text-[#eca8d6]" />
                <h3 className="font-display font-bold text-white text-base">Python 3.12+ CLI</h3>
              </div>
              <p className="text-xs lg:text-sm text-white/60 leading-relaxed">
                Run dataset, model, provenance, and drift checks with explicit coverage.
              </p>
            </div>

            <div className="p-6 border border-white/15 bg-black/60 rounded-xl backdrop-blur-md">
              <div className="flex items-center gap-2 mb-2">
                <Code2 className="w-4 h-4 text-[#eca8d6]" />
                <h3 className="font-display font-bold text-white text-base">Report artifacts</h3>
              </div>
              <p className="text-xs lg:text-sm text-white/60 leading-relaxed">
                Export findings, coverage, evidence, and an optional signed report manifest.
              </p>
            </div>

            <div className="p-6 border border-white/15 bg-black/60 rounded-xl backdrop-blur-md">
              <div className="flex items-center gap-2 mb-2">
                <Cpu className="w-4 h-4 text-[#eca8d6]" />
                <h3 className="font-display font-bold text-white text-base">Input formats</h3>
              </div>
              <p className="text-xs lg:text-sm text-white/60 leading-relaxed">
                Assess COCO, YOLO, VOC, ImageFolder, ONNX, TorchScript, and supported weights files.
              </p>
            </div>

            <div className="p-6 border border-white/15 bg-black/60 rounded-xl backdrop-blur-md">
              <div className="flex items-center gap-2 mb-2">
                <ShieldAlert className="w-4 h-4 text-[#eca8d6]" />
                <h3 className="font-display font-bold text-white text-base">Standalone verifier</h3>
              </div>
              <p className="text-xs lg:text-sm text-white/60 leading-relaxed">
                <code className="text-white font-mono text-xs">visionsentinel verify</code> checks signed ledgers against a trust root offline.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
