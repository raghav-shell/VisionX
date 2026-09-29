"use client";

import React, { useEffect, useRef, useState } from "react";

export default function SignalMetrics() {
  const sparklineRef1 = useRef<HTMLCanvasElement | null>(null);
  const sparklineRef2 = useRef<HTMLCanvasElement | null>(null);
  const sparklineRef3 = useRef<HTMLCanvasElement | null>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0.5);

  useEffect(() => {
    const handleScroll = () => {
      if (!sectionRef.current) return;
      const rect = sectionRef.current.getBoundingClientRect();
      const windowHeight = window.innerHeight;
      const progress = (windowHeight - rect.top) / (windowHeight + rect.height);
      setScrollProgress(Math.min(Math.max(progress, 0), 1));
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Animate mini sparklines dynamically on frame loop
  useEffect(() => {
    let animId: number;
    let t = 0;

    const render = () => {
      t += 0.04;

      const drawSparkline = (
        canvas: HTMLCanvasElement | null,
        color: string,
        pattern: (i: number, points: number, height: number) => number
      ) => {
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const width = (canvas.width = canvas.parentElement?.clientWidth || 220);
        const height = (canvas.height = 36);

        const points = 26;
        const data: number[] = [];
        for (let i = 0; i < points; i++) {
          data.push(pattern(i, points, height));
        }

        ctx.clearRect(0, 0, width, height);
        ctx.beginPath();
        ctx.moveTo(0, data[0]);

        for (let i = 1; i < points; i++) {
          const x = (i / (points - 1)) * width;
          ctx.lineTo(x, data[i]);
        }

        ctx.strokeStyle = color;
        ctx.lineWidth = 1.8;
        ctx.stroke();

        ctx.lineTo(width, height);
        ctx.lineTo(0, height);
        ctx.closePath();
        const grad = ctx.createLinearGradient(0, 0, 0, height);
        grad.addColorStop(0, `${color}33`);
        grad.addColorStop(1, `${color}00`);
        ctx.fillStyle = grad;
        ctx.fill();
      };

      drawSparkline(sparklineRef1.current, "#eca8d6", (i, points, h) => {
        return h * 0.65 - (i / points) * (h * 0.35) + Math.sin(i * 0.5 + t) * 4;
      });

      drawSparkline(sparklineRef2.current, "#91dcbc", (i, points, h) => {
        const spike = Math.exp(-Math.pow(i - 18, 2) / 3) * (h * 0.5);
        return h * 0.65 - spike + Math.sin(i * 0.8 + t * 0.7) * 2;
      });

      drawSparkline(sparklineRef3.current, "#79cdf9", (i, points, h) => {
        return h * 0.5 + Math.sin(i * 0.4 + t * 0.5) * 5 + Math.cos(i * 0.2 + t) * 3;
      });

      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, []);

  const graphParallaxY = (scrollProgress - 0.5) * -35;

  return (
    <section
      ref={sectionRef}
      id="metrics"
      className="relative py-28 lg:py-36 bg-[#040406] text-white overflow-hidden border-t border-white/10"
    >
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        {/* Section Header */}
        <div className="grid lg:grid-cols-12 gap-8 mb-20 lg:mb-32">
          <div className="lg:col-span-8">
            <div className="flex items-center gap-4 mb-6">
              <span className="flex items-center gap-2 px-3 py-1 bg-[#eca8d6]/10 text-[#eca8d6] text-xs font-mono rounded-full border border-[#eca8d6]/20">
                <span className="w-2 h-2 rounded-full bg-[#eca8d6] animate-pulse"></span>
                LIVE PROTOCOL TELEMETRY
              </span>
            </div>
            <h2 className="text-6xl md:text-7xl lg:text-[115px] font-display font-bold tracking-tight leading-[0.92] text-white">
              Mathematical<br />
              <span className="text-white/40">rigor, zero hype.</span>
            </h2>
          </div>
          <div className="lg:col-span-4 flex items-end">
            <p className="text-base lg:text-lg text-white/60 leading-relaxed font-normal">
              Continuous empirical drift tracking across high-dimensional latent embeddings.
              Detect subtle distribution corruption before downstream predictions fail.
            </p>
          </div>
        </div>

        {/* 3D Real-Time Metric Graph Graphic with Scroll Parallax */}
        <div
          className="relative w-full mb-12 rounded-2xl overflow-hidden border border-white/10 bg-black/60 shadow-2xl transition-transform duration-300 ease-out will-change-transform"
          style={{
            transform: `translateY(${graphParallaxY}px)`,
          }}
        >
          <img
            src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/real-time-graph-INFmn3u0MlUwvNPynoIhwxtPaPjxM5.png"
            alt="Real-time multi-dimensional drift visual"
            className="w-full h-auto object-cover select-none pointer-events-none"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#040406] via-transparent to-transparent pointer-events-none"></div>
        </div>

        {/* Live Sparkline Stats Bento */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Card 1: Trigger Anomaly Score */}
          <div className="bg-[#09090b] border border-white/15 p-8 lg:p-10 rounded-2xl flex flex-col justify-between hover:border-white/30 transition-all duration-300 group">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-mono text-white/50 uppercase tracking-wider">
                  Module B · Trojan Detection
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-red-500/10 text-red-400 border border-red-500/20">
                  FLAGGED
                </span>
              </div>
              <div className="text-4xl lg:text-5xl font-display font-bold text-white tracking-tight mb-2 flex items-baseline gap-2">
                <span>4.92</span>
                <span className="text-xs font-mono text-white/40 font-normal">Anomaly Index</span>
              </div>
              <p className="text-xs text-white/50 mb-6">
                L1 norm deviation against median absolute deviation (Threshold: 2.13).
              </p>
            </div>
            <div>
              <canvas ref={sparklineRef1} className="w-full h-9 block mb-4" />
              <div className="flex justify-between items-center text-xs font-mono text-white/40 pt-2 border-t border-white/10">
                <span>Target: Class #4</span>
                <span className="text-[#eca8d6]">p &lt; 0.001</span>
              </div>
            </div>
          </div>

          {/* Card 2: Wasserstein Drift */}
          <div className="bg-[#09090b] border border-white/15 p-8 lg:p-10 rounded-2xl flex flex-col justify-between hover:border-white/30 transition-all duration-300 group">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-mono text-white/50 uppercase tracking-wider">
                  Module D · Embedding Drift
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  STABLE
                </span>
              </div>
              <div className="text-4xl lg:text-5xl font-display font-bold text-white tracking-tight mb-2 flex items-baseline gap-2">
                <span>0.042</span>
                <span className="text-xs font-mono text-white/40 font-normal">Wasserstein Dist</span>
              </div>
              <p className="text-xs text-white/50 mb-6">
                Earth Mover's Distance between baseline features and incoming inference batch.
              </p>
            </div>
            <div>
              <canvas ref={sparklineRef2} className="w-full h-9 block mb-4" />
              <div className="flex justify-between items-center text-xs font-mono text-white/40 pt-2 border-t border-white/10">
                <span>KS-Test Statistic</span>
                <span className="text-emerald-400">P = 0.984</span>
              </div>
            </div>
          </div>

          {/* Card 3: Cryptographic Merkle Latency */}
          <div className="bg-[#09090b] border border-white/15 p-8 lg:p-10 rounded-2xl flex flex-col justify-between hover:border-white/30 transition-all duration-300 group">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-mono text-white/50 uppercase tracking-wider">
                  Module E · Ledger Commit
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  APPEND-ONLY
                </span>
              </div>
              <div className="text-4xl lg:text-5xl font-display font-bold text-white tracking-tight mb-2 flex items-baseline gap-2">
                <span>&lt;0.2ms</span>
                <span className="text-xs font-mono text-white/40 font-normal">Proof Latency</span>
              </div>
              <p className="text-xs text-white/50 mb-6">
                RFC 6962 SHA-256 consistency and inclusion proof generation on air-gapped ledger.
              </p>
            </div>
            <div>
              <canvas ref={sparklineRef3} className="w-full h-9 block mb-4" />
              <div className="flex justify-between items-center text-xs font-mono text-white/40 pt-2 border-t border-white/10">
                <span>Tree Depth: 18</span>
                <span className="text-[#79cdf9]">100% Verified</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
