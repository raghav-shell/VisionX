"use client";

import React from "react";
import Link from "next/link";
import { ArrowUpRight, ArrowUp } from "lucide-react";
import VisionXLogo from "./VisionXLogo";

export default function Footer() {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <footer className="relative bg-black text-white overflow-hidden">
      {/* Bioluminescent Panoramic Landscape Artwork matching source */}
      <div className="relative w-full h-[360px] md:h-[480px] lg:h-[560px] overflow-hidden">
        <img
          src="/images/upscaled-10.png"
          alt="Bioluminescent floral landscape"
          className="w-full h-full object-cover object-center select-none pointer-events-none"
        />

        {/* Top Edge Gradient: seamless transition from previous section */}
        <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-black via-black/60 to-transparent pointer-events-none" />

        {/* Bottom Edge Gradient: seamless transition into pure black footer */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-black/20 to-black pointer-events-none" />

        {/* Horizontal Vignette Scrims */}
        <div className="absolute inset-0 bg-gradient-to-r from-black/60 via-transparent to-black/60 pointer-events-none" />
      </div>

      {/* Footer Navigation Columns */}
      <div className="relative z-10 max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="py-16 lg:py-20">
          <div className="grid grid-cols-2 md:grid-cols-6 gap-12 lg:gap-8">
            {/* Brand Column (Spans 2) */}
            <div className="col-span-2">
              <Link href="/" className="inline-flex items-center gap-3 mb-6 group">
                <VisionXLogo size={32} />
                <span className="text-2xl font-display font-bold text-white tracking-wider flex items-center">
                  Vision<span className="bg-gradient-to-r from-[#eca8d6] via-[#c597eb] to-[#a78bfa] bg-clip-text text-transparent font-extrabold">X</span>
                </span>
              </Link>

              <p className="text-white/50 leading-relaxed mb-8 max-w-sm text-sm font-sans">
                Air-gapped assurance across training datasets, model weights, and inference records.
                Findings link to evidence, while coverage states show what could not be assessed.
              </p>

              <div className="flex flex-wrap gap-6 text-sm text-white/50 font-sans">
                <a
                  href="#console"
                  className="hover:text-white transition-colors flex items-center gap-1 group"
                >
                  <span>CLI examples</span>
                  <ArrowUpRight className="w-3 h-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-[#eca8d6]" />
                </a>
                <Link
                  href="/workspace"
                  className="hover:text-white transition-colors flex items-center gap-1 group"
                >
                  <span>Studio</span>
                  <ArrowUpRight className="w-3 h-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-[#eca8d6]" />
                </Link>
                <a
                  href="#infra"
                  className="hover:text-white transition-colors flex items-center gap-1 group"
                >
                  <span>Offline design</span>
                  <ArrowUpRight className="w-3 h-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-[#eca8d6]" />
                </a>
              </div>
            </div>

            {/* Column 1: Modules / Product */}
            <div>
              <h3 className="text-sm font-medium text-white mb-6 font-display">
                Modules
              </h3>
              <ul className="space-y-4 text-sm text-white/50 font-sans">
                <li>
                  <a href="#capabilities" className="hover:text-white transition-colors">
                    Dataset Integrity
                  </a>
                </li>
                <li>
                  <a href="#capabilities" className="hover:text-white transition-colors">
                    Model Assurance
                  </a>
                </li>
                <li>
                  <a href="#capabilities" className="hover:text-white transition-colors">
                    Signed Inference Ledger
                  </a>
                </li>
                <li>
                  <a href="#signals" className="hover:text-white transition-colors">
                    Statistical Drift
                  </a>
                </li>
              </ul>
            </div>

            {/* Column 2: Developers / Engine */}
            <div>
              <h3 className="text-sm font-medium text-white mb-6 font-display">
                Developers
              </h3>
              <ul className="space-y-4 text-sm text-white/50 font-sans">
                <li>
                  <a href="#sdk" className="hover:text-white transition-colors">
                    Local workflow
                  </a>
                </li>
                <li>
                  <a href="#sdk" className="hover:text-white transition-colors">
                    Python CLI
                  </a>
                </li>
                <li>
                  <a href="#sdk" className="hover:text-white transition-colors">
                    Standalone verifier
                  </a>
                </li>
                <li>
                  <a href="#infra" className="hover:text-white transition-colors">
                    Bounded execution
                  </a>
                </li>
              </ul>
            </div>

            {/* Column 3: Team & Hackathon */}
            <div>
              <h3 className="text-sm font-medium text-white mb-6 font-display">
                Project
              </h3>
              <ul className="space-y-4 text-sm text-white/50 font-sans">
                <li>
                  <span className="text-white/70">VisionX Core Team</span>
                </li>
                <li>
                  <span className="text-white/50">SIH PS 26228</span>
                </li>
                <li>
                  <a href="https://github.com/raghav-shell/VisionX" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">
                    View Source
                  </a>
                </li>
                <li>
                  <Link href="/workspace" className="text-[#eca8d6] hover:underline">
                    Explore demo
                  </Link>
                </li>
              </ul>
            </div>

            {/* Column 4: Standards & validation */}
            <div>
              <h3 className="text-sm font-medium text-white mb-6 font-display">
                Trust &amp; Evidence
              </h3>
              <ul className="space-y-4 text-sm text-white/50 font-sans">
                <li>
                  <a href="#security" className="hover:text-white transition-colors">
                    RFC 8785 C14N
                  </a>
                </li>
                <li>
                  <a href="#security" className="hover:text-white transition-colors">
                    RFC 6962 Merkle
                  </a>
                </li>
                <li>
                  <a href="#security" className="hover:text-white transition-colors">
                    Coverage and limits
                  </a>
                </li>
                <li>
                  <a href="#validation" className="hover:text-white transition-colors">
                    Validation Tests
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="py-8 border-t border-white/10 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-white/40">
            © 2026 VisionX. Smart India Hackathon computer-vision assurance project.
          </p>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 text-sm text-white/40 font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Demo workspace available</span>
            </div>

            <button
              onClick={scrollToTop}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.08] hover:border-[#eca8d6]/40 hover:text-white text-xs font-mono text-white/60 transition-all"
            >
              <span>Back to Top</span>
              <ArrowUp className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
}
