"use client";

import React, { useState, useEffect, useRef } from "react";

export default function Infrastructure() {
  const [scrollProgress, setScrollProgress] = useState(0.5);
  const sectionRef = useRef<HTMLElement>(null);

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

  const sphereRotation = (scrollProgress - 0.5) * 25;
  const sphereTranslateY = (scrollProgress - 0.5) * -30;

  return (
    <section
      ref={sectionRef}
      id="infra"
      className="relative py-32 lg:py-44 overflow-hidden bg-black border-t border-white/10"
    >
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        {/* Section Header */}
        <div className="mb-20">
          <span className="inline-flex items-center gap-4 text-sm font-mono text-white/50 mb-8 uppercase tracking-wider">
            <span className="w-12 h-px bg-[#eca8d6]"></span>
            Enclave Architecture
          </span>
          <div className="grid lg:grid-cols-[auto_1fr] gap-8 lg:gap-16 items-center">
            {/* World Network Graphic with Parallax & Slow Rotation */}
            <div
              className="w-48 lg:w-72 xl:w-80 shrink-0 transition-transform duration-300 ease-out will-change-transform"
              style={{
                transform: `translateY(${sphereTranslateY}px) rotate(${sphereRotation}deg)`,
              }}
            >
              <img
                src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/world-3i68QNWJwmO7W19ztZWbevAwJQHzYL.png"
                alt="Cryptographic network sphere"
                className="w-full h-full object-contain object-center drop-shadow-[0_0_40px_rgba(236,168,214,0.22)] animate-float-slow"
              />
            </div>

            {/* Typography */}
            <div>
              <h2 className="text-6xl md:text-7xl lg:text-[115px] font-display font-bold tracking-tight leading-[0.9] text-white">
                Offline by<br />
                <span className="text-white/40">default.</span>
              </h2>
              <p className="mt-8 text-lg lg:text-xl text-white/65 leading-relaxed max-w-xl font-normal">
                Audits execute in zero-network environments. Enforced at both the Linux kernel level
                (<code className="font-mono text-sm px-1.5 py-0.5 rounded bg-white/10 text-white">unshare -rn</code>) and
                via programmatic in-process socket guards that intercept DNS and connect calls.
              </p>
            </div>
          </div>
        </div>

        {/* Dynamic Interactive Visuals */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Animated Connecting Nodes Grid */}
          <div className="lg:col-span-2 relative p-8 lg:p-14 border border-white/15 bg-[#09090b] rounded-xl overflow-hidden min-h-[380px] flex flex-col justify-end">
            <div className="absolute inset-0 opacity-75">
              <svg className="absolute inset-0 w-full h-full pointer-events-none">
                {/* Connecting Lines */}
                <line x1="12%" y1="18%" x2="36%" y2="18%" className="connecting-line" style={{ animationDelay: "0s" }} />
                <line x1="36%" y1="18%" x2="60%" y2="18%" className="connecting-line" style={{ animationDelay: "0.2s" }} />
                <line x1="60%" y1="18%" x2="84%" y2="18%" className="connecting-line" style={{ animationDelay: "0.4s" }} />
                
                <line x1="12%" y1="50%" x2="36%" y2="50%" className="connecting-line" style={{ animationDelay: "0.6s" }} />
                <line x1="36%" y1="50%" x2="60%" y2="50%" className="connecting-line" style={{ animationDelay: "0.8s" }} />
                <line x1="60%" y1="50%" x2="84%" y2="50%" className="connecting-line" style={{ animationDelay: "1.0s" }} />

                <line x1="12%" y1="82%" x2="36%" y2="82%" className="connecting-line" style={{ animationDelay: "1.2s" }} />
                <line x1="36%" y1="82%" x2="60%" y2="82%" className="connecting-line" style={{ animationDelay: "1.4s" }} />
                <line x1="60%" y1="82%" x2="84%" y2="82%" className="connecting-line" style={{ animationDelay: "1.6s" }} />

                {/* Diagonal Connections */}
                <line x1="12%" y1="18%" x2="36%" y2="50%" className="connecting-line" style={{ animationDelay: "1.8s" }} />
                <line x1="36%" y1="50%" x2="60%" y2="82%" className="connecting-line" style={{ animationDelay: "2.0s" }} />
                <line x1="36%" y1="18%" x2="60%" y2="50%" className="connecting-line" style={{ animationDelay: "2.2s" }} />
                <line x1="60%" y1="50%" x2="84%" y2="82%" className="connecting-line" style={{ animationDelay: "2.4s" }} />
              </svg>

              {/* Glowing Pulse Nodes with hover tooltips */}
              {[
                { x: "12%", y: "18%", delay: "0s", label: "Dataset Ingest" },
                { x: "36%", y: "18%", delay: "0.3s", label: "Hash Verifier" },
                { x: "60%", y: "18%", delay: "0.6s", label: "Trigger Synthesizer" },
                { x: "84%", y: "18%", delay: "0.9s", label: "Weight Check" },
                { x: "12%", y: "50%", delay: "0.4s", label: "S3 Sandbox" },
                { x: "36%", y: "50%", delay: "0.7s", label: "Peer Cred Auth" },
                { x: "60%", y: "50%", delay: "1.0s", label: "Drift Monitor" },
                { x: "84%", y: "50%", delay: "1.3s", label: "Capability Plan" },
                { x: "12%", y: "82%", delay: "0.8s", label: "Ed25519 Signer" },
                { x: "36%", y: "82%", delay: "1.1s", label: "Merkle Tree RFC 6962" },
                { x: "60%", y: "82%", delay: "1.4s", label: "visionx-ledgerd Daemon" },
                { x: "84%", y: "82%", delay: "1.7s", label: "Four-Eyes MultiSig" },
              ].map((node, i) => (
                <div
                  key={i}
                  className="absolute group/node -translate-x-1/2 -translate-y-1/2 cursor-pointer z-10"
                  style={{ left: node.x, top: node.y }}
                >
                  <div
                    className="w-3 h-3 rounded-full bg-[#eca8d6] animate-pulse-glow"
                    style={{ animationDelay: node.delay }}
                  />
                  <div className="absolute bottom-5 left-1/2 -translate-x-1/2 px-2.5 py-1 rounded bg-black/90 border border-white/20 text-[10px] font-mono whitespace-nowrap text-white opacity-0 group-hover/node:opacity-100 transition-opacity pointer-events-none shadow-xl">
                    {node.label}
                  </div>
                </div>
              ))}
            </div>

            <div className="relative z-10">
              <div className="flex items-baseline gap-3 mb-2">
                <span className="text-7xl lg:text-9xl font-display font-bold text-white tracking-tight leading-none">
                  0
                </span>
                <span className="text-xl lg:text-2xl text-white/50 font-display">
                  external sockets
                </span>
              </div>
              <p className="text-sm lg:text-base text-white/60 max-w-md font-normal">
                Strict egress isolation. Zero external telemetry or outbound connections during audits.
              </p>
            </div>
          </div>

          {/* Right Column Metric Cards */}
          <div className="flex flex-col gap-6">
            <div className="p-8 border border-white/15 bg-[#09090b] rounded-xl flex-1 flex flex-col justify-center hover:border-white/30 transition-all duration-300 group">
              <span className="text-5xl lg:text-6xl font-display font-bold text-white tracking-tight group-hover:text-[#eca8d6] transition-colors">
                100%
              </span>
              <span className="text-sm font-mono text-white/50 mt-2 uppercase tracking-wider">
                Deterministic C99
              </span>
              <p className="text-xs text-white/40 mt-3 leading-relaxed">
                Zero garbage collection spikes. Fixed memory arena allocators for real-time edge compliance.
              </p>
            </div>

            <div className="p-8 border border-white/15 bg-[#09090b] rounded-xl flex-1 flex flex-col justify-center hover:border-white/30 transition-all duration-300 group">
              <span className="text-5xl lg:text-6xl font-display font-bold text-white tracking-tight group-hover:text-[#c597eb] transition-colors">
                &lt;200µs
              </span>
              <span className="text-sm font-mono text-white/50 mt-2 uppercase tracking-wider">
                Local IPC Latency
              </span>
              <p className="text-xs text-white/40 mt-3 leading-relaxed">
                Kernel-level UNIX domain socket communication authenticated via <code className="text-[#eca8d6]">SO_PEERCRED</code>.
              </p>
            </div>
          </div>
        </div>

        {/* Bottom Nodes Status Row */}
        <div className="mt-12 grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { region: "Local Host Daemon", status: "Active (UNIX)", nodes: "visionx-ledgerd", ping: "0.1ms" },
            { region: "S3 Sandboxed Worker", status: "Hardened", nodes: "seccomp-bpf", ping: "Active" },
            { region: "Four-Eyes Signer A", status: "Key Loaded", nodes: "Ed25519 Detached", ping: "Ready" },
            { region: "Four-Eyes Signer B", status: "Dual Approver", nodes: "Quorum Required", ping: "Ready" },
          ].map((item, i) => (
            <div
              key={i}
              className="p-6 border border-white/10 bg-[#09090b]/60 rounded-xl hover:border-white/25 transition-all duration-300"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#eca8d6] animate-pulse"></span>
                  <span className="text-xs font-mono text-white/40 uppercase tracking-wider">
                    {item.status}
                  </span>
                </div>
                <span className="text-[11px] font-mono text-[#eca8d6]">{item.ping}</span>
              </div>
              <span className="font-display font-bold text-base text-white block mb-1">
                {item.region}
              </span>
              <span className="text-xs text-white/50 font-mono">{item.nodes}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
