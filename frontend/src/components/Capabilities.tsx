"use client";

import React, { useEffect, useRef } from "react";
import { Database, ShieldAlert, FileCheck2, Activity, ArrowRight } from "lucide-react";

export default function Capabilities() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Subtle interactive particle canvas for Card 01
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 600);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 450);

    const particles: Array<{
      x: number;
      y: number;
      vx: number;
      vy: number;
      radius: number;
      alpha: number;
    }> = [];

    for (let i = 0; i < 45; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: Math.random() * 1.5 + 1,
        alpha: Math.random() * 0.5 + 0.2,
      });
    }

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Draw subtle grid points
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(236, 168, 214, ${p.alpha})`;
        ctx.fill();

        // Connect nearby particles
        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dist = Math.hypot(p.x - p2.x, p.y - p2.y);
          if (dist < 80) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `rgba(236, 168, 214, ${0.15 * (1 - dist / 80)})`;
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };

    window.addEventListener("resize", handleResize);
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return (
    <section id="capabilities" className="relative py-28 lg:py-36 overflow-hidden bg-black">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        {/* Section Header */}
        <div className="relative mb-20 lg:mb-28">
          <div className="grid lg:grid-cols-12 gap-8 items-end">
            <div className="lg:col-span-7">
              <span className="inline-flex items-center gap-3 text-sm font-mono text-white/50 mb-6 uppercase tracking-wider">
                <span className="w-12 h-px bg-[#eca8d6]"></span>
                Capabilities
              </span>
              <h2 className="text-5xl md:text-7xl lg:text-[110px] font-display font-bold tracking-tight leading-[0.9] text-white">
                Find the risk.<br />
                <span className="text-white/40">Keep the evidence.</span>
              </h2>
            </div>
            <div className="lg:col-span-5 lg:pb-3">
              <p className="text-lg md:text-xl text-white/60 leading-relaxed font-normal">
                Assess datasets, models, inference records, and distribution drift. Each check
                reports whether it ran, had limited access, or could not assess the asset.
              </p>
            </div>
          </div>
        </div>

        {/* Bento Grid */}
        <div className="grid lg:grid-cols-12 gap-6">
          {/* Card 01 - Large Bento Card with Particle Canvas and Art */}
          <div className="lg:col-span-12 relative bg-[#0a0a0c] border border-white/15 min-h-[500px] overflow-hidden group transition-all duration-700 flex flex-col lg:flex-row hover:border-white/30 rounded-xl">
            <div className="relative flex-1 p-8 lg:p-14 bg-gradient-to-br from-black via-[#0c0c10] to-black z-10">
              <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" />
              <div className="relative z-10">
                <div className="flex items-center gap-3 mb-6">
                  <span className="font-mono text-xs px-2 py-0.5 rounded border border-[#eca8d6]/30 text-[#eca8d6] bg-[#eca8d6]/10">
                    MODULE A
                  </span>
                  <span className="font-mono text-sm text-white/40">01</span>
                </div>
                <h3 className="text-3xl lg:text-5xl font-display font-bold text-white mb-6 group-hover:translate-x-1 transition-transform duration-500">
                  Dataset integrity &amp; contributor risk
                </h3>
                <p className="text-base lg:text-lg text-white/65 leading-relaxed max-w-xl mb-10">
                  Detect near-duplicate samples, label conflicts, and suspicious image artifacts.
                  Link findings to contributors and review the underlying evidence before acting.
                </p>
                <p className="mb-3 font-mono text-[10px] uppercase tracking-wider text-white/40">
                  Illustrative demo figures · not measured benchmarks
                </p>
                <div className="flex flex-wrap gap-8 items-baseline pt-4 border-t border-white/10">
                  <div>
                    <span className="text-4xl lg:text-6xl font-display font-bold text-white">99.8%</span>
                    <span className="block text-xs text-white/50 font-mono mt-1 uppercase">
                      Example poison recall
                    </span>
                  </div>
                  <div>
                    <span className="text-4xl lg:text-6xl font-display font-bold text-[#eca8d6]">0.00</span>
                    <span className="block text-xs text-white/50 font-mono mt-1 uppercase">
                      Example clean false alarms
                    </span>
                  </div>
                  <div>
                    <span className="text-4xl lg:text-6xl font-display font-bold text-white/90">5 Tiers</span>
                    <span className="block text-xs text-white/50 font-mono mt-1 uppercase">
                      Example contributor hierarchy
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Art Frame */}
            <div className="hidden lg:block relative w-[40%] shrink-0 overflow-hidden border-l border-white/10">
              <img
                src="/images/upscaled-12.png"
                alt="Cybernetic vision architecture"
                className="absolute inset-0 w-full h-full object-cover object-center group-hover:scale-105 transition-transform duration-700"
                style={{ transform: "scaleX(-1)" }}
              />
              <div className="absolute inset-0 bg-gradient-to-r from-black via-black/20 to-transparent"></div>
            </div>
          </div>

          {/* Card 02 - Model Integrity (Neural Cleanse) */}
          <div className="lg:col-span-4 relative p-8 lg:p-10 border border-white/15 bg-gradient-to-b from-[#0a0a0d] to-black rounded-xl hover:border-[#eca8d6]/40 transition-all duration-500 group flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-8">
                <span className="font-mono text-xs px-2 py-0.5 rounded border border-white/20 text-white/70">
                  MODULE B
                </span>
                <span className="font-mono text-sm text-white/30">02</span>
              </div>
              <h3 className="text-2xl lg:text-3xl font-display font-bold text-white mb-4 group-hover:text-[#eca8d6] transition-colors">
                Model backdoor indicators
              </h3>
              <p className="text-sm lg:text-base text-white/60 leading-relaxed mb-6">
                Probe model behavior and reconstruct possible triggers when the model provides the
                needed access. Missing gradients or other prerequisites remain visible in coverage.
              </p>
            </div>
            <div className="pt-6 border-t border-white/10">
              <div className="flex flex-wrap justify-between items-baseline gap-2">
                <span className="text-3xl font-display font-bold text-white">4.92 vs 2.13</span>
                <span className="text-xs font-mono text-[#eca8d6]">Demo signal</span>
              </div>
              <span className="text-xs text-white/40 block mt-1">Illustrative anomaly index comparison</span>
            </div>
          </div>

          {/* Card 03 - Provenance Seal */}
          <div className="lg:col-span-4 relative p-8 lg:p-10 border border-white/15 bg-gradient-to-b from-[#0a0a0d] to-black rounded-xl hover:border-[#eca8d6]/40 transition-all duration-500 group flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-8">
                <span className="font-mono text-xs px-2 py-0.5 rounded border border-white/20 text-white/70">
                  MODULE C
                </span>
                <span className="font-mono text-sm text-white/30">03</span>
              </div>
              <h3 className="text-2xl lg:text-3xl font-display font-bold text-white mb-4 group-hover:text-[#eca8d6] transition-colors">
                Cryptographic Provenance
              </h3>
              <p className="text-sm lg:text-base text-white/60 leading-relaxed mb-6">
                Verify signed inference records against trusted keys and Merkle checkpoints.
                External anchors, when supplied, also reveal truncated or rewritten history.
              </p>
            </div>
            <div className="pt-6 border-t border-white/10">
              <div className="flex flex-wrap justify-between items-baseline gap-2">
                <span className="text-3xl font-display font-bold text-white">&lt;0.2ms</span>
                <span className="text-xs font-mono text-[#eca8d6]">Demo timing</span>
              </div>
              <span className="text-xs text-white/40 block mt-1">Illustrative proof latency; not a benchmark</span>
            </div>
          </div>

          {/* Card 04 - Distribution Drift */}
          <div className="lg:col-span-4 relative p-8 lg:p-10 border border-white/15 bg-gradient-to-b from-[#0a0a0d] to-black rounded-xl hover:border-[#eca8d6]/40 transition-all duration-500 group flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-8">
                <span className="font-mono text-xs px-2 py-0.5 rounded border border-white/20 text-white/70">
                  MODULE D
                </span>
                <span className="font-mono text-sm text-white/30">04</span>
              </div>
              <h3 className="text-2xl lg:text-3xl font-display font-bold text-white mb-4 group-hover:text-[#eca8d6] transition-colors">
                Distribution drift
              </h3>
              <p className="text-sm lg:text-base text-white/60 leading-relaxed mb-6">
                Compare incoming images with a trusted reference across interpretable visual
                features. Review which shifts are significant before investigating their cause.
              </p>
            </div>
            <div className="pt-6 border-t border-white/10">
              <div className="flex flex-wrap justify-between items-baseline gap-2">
                <span className="text-3xl font-display font-bold text-white">2000 Iter</span>
                <span className="text-xs font-mono text-[#eca8d6]">Demo setting</span>
              </div>
              <span className="text-xs text-white/40 block mt-1">Illustrative permutation count</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
