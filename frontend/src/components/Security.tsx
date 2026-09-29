"use client";

import React, { useState } from "react";
import { Shield, Lock, Eye, UserCheck } from "lucide-react";

export default function Security() {
  const [activeFeature, setActiveFeature] = useState(0);

  const securityFeatures = [
    {
      title: "Bounded model execution",
      desc: "Untrusted model runtimes execute in a worker with resource limits and restrictions on sockets, subprocesses, and file writes.",
      icon: Shield,
      image: "/images/isolated.jpg",
      imageAlt: "Organic shield representing isolated execution",
      stat: "Worker isolation",
      detail: "Resource limits and restricted operations",
    },
    {
      title: "Trusted signing keys",
      desc: "The CLI signs reports or inference ledgers with operator-supplied Ed25519 keys. Verification uses a supplied trust root.",
      icon: Lock,
      image: "/images/encrypted.jpg",
      imageAlt: "Glowing woven lock representing protected signing keys",
      stat: "Ed25519",
      detail: "Operator-supplied signing keys and trust roots",
    },
    {
      title: "Evidence-led decisions",
      desc: "The risk policy links recommended dispositions to findings and coverage. Reviewers can inspect the underlying evidence and limitations.",
      icon: UserCheck,
      image: "/images/permissions.jpg",
      imageAlt: "Woven access token representing independent authorization",
      stat: "2-person demo",
      detail: "Illustrative review flow; not enforced by the scanner",
    },
    {
      title: "Verifiable ledger history",
      desc: "Signed inference records and Merkle checkpoints can be verified offline. An external anchor, when provided, helps reveal tail truncation.",
      icon: Eye,
      image: "/images/audit.jpg",
      imageAlt: "Glowing eye representing the inspectable audit trail",
      stat: "RFC 6962",
      detail: "Optional external anchor verification",
    },
  ];

  return (
    <section id="security" className="relative py-28 lg:py-36 overflow-hidden bg-[#030304] border-t border-white/10">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        {/* Header */}
        <div className="mb-20">
          <span className="inline-flex items-center gap-4 text-sm font-mono text-white/50 mb-8 uppercase tracking-wider">
            <span className="w-12 h-px bg-[#eca8d6]"></span>
            Assurance boundaries
          </span>
          <h2 className="text-5xl md:text-7xl lg:text-[115px] font-display font-bold tracking-tight leading-[0.9] mb-8 text-white">
            Trust the<br />
            <span className="text-white/40">evidence.</span>
          </h2>
          <p className="text-lg lg:text-xl text-white/60 leading-relaxed max-w-2xl font-normal">
            VisionX shows what each check observed and where its conclusion stops. Signed records
            and optional external anchors make changes to inference history detectable.
          </p>
        </div>

        {/* 2-Column Grid */}
        <div className="grid lg:grid-cols-12 gap-8 items-stretch">
          {/* Left Hero Card */}
          <div className="lg:col-span-6 relative p-8 lg:p-14 border border-white/15 bg-gradient-to-br from-[#0c0c10] via-black to-[#08080a] rounded-xl flex flex-col justify-between overflow-hidden">
            <img
              key={securityFeatures[activeFeature].image}
              src={securityFeatures[activeFeature].image}
              alt={securityFeatures[activeFeature].imageAlt}
              className="absolute right-[-8%] bottom-[14%] w-[78%] h-[50%] lg:top-[17%] lg:bottom-auto lg:w-[64%] lg:h-[68%] object-contain opacity-45 lg:opacity-100 pointer-events-none select-none animate-fade-slide-in"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/30 to-transparent pointer-events-none" />
            <div className="relative z-10">
              <span className="font-mono text-xs text-[#eca8d6] uppercase tracking-wider px-2.5 py-1 rounded bg-[#eca8d6]/10 border border-[#eca8d6]/20">
                ILLUSTRATIVE ANCHORED LEDGER
              </span>
              <div className="mt-8 mb-6">
                <span className="text-7xl lg:text-9xl font-display font-bold text-white leading-none block">
                  0
                </span>
                <span className="text-base lg:text-lg text-white/60 block mt-2">
                  example unwitnessed gaps
                </span>
              </div>
              <p className="mb-3 font-mono text-[10px] uppercase tracking-wider text-white/45">
                Static demo value · not a live security metric
              </p>
              <p className="text-sm lg:text-base text-white/60 leading-relaxed max-w-full lg:max-w-[58%] font-normal">
                {securityFeatures[activeFeature].desc}
              </p>
            </div>

            <div className="relative z-10 pt-8 mt-8 border-t border-white/10 flex flex-wrap gap-2">
              {["Bounded worker", "Signed reports", "Coverage states", "Merkle checkpoints", "External anchors"].map((pill) => (
                <span
                  key={pill}
                  className="px-3 py-1 border border-white/10 rounded-full text-xs font-mono text-white/60 bg-white/[0.02]"
                >
                  {pill}
                </span>
              ))}
            </div>
          </div>

          {/* Right Interactive Feature Cards */}
          <div className="lg:col-span-6 flex flex-col gap-4 justify-between">
            {securityFeatures.map((feat, idx) => {
              const Icon = feat.icon;
              const isSelected = activeFeature === idx;
              return (
                <button
                  type="button"
                  aria-pressed={isSelected}
                  key={feat.title}
                  onClick={() => setActiveFeature(idx)}
                  className={`w-full text-left p-6 border rounded-xl transition-all duration-300 cursor-pointer ${
                    isSelected
                      ? "border-[#eca8d6]/60 bg-white/[0.04] shadow-md shadow-black"
                      : "border-white/10 bg-black/40 hover:border-white/25"
                  }`}
                >
                  <div className="flex items-start gap-4">
                    <div
                      className={`shrink-0 w-11 h-11 rounded-lg flex items-center justify-center transition-colors ${
                        isSelected
                          ? "bg-[#eca8d6] text-black font-semibold"
                          : "border border-white/15 bg-white/5 text-white/70"
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                        <h3 className="font-display font-semibold text-lg text-white">
                          {feat.title}
                        </h3>
                        <span className="font-mono text-xs text-[#eca8d6]">
                          {feat.stat}
                        </span>
                      </div>
                      <p className="text-xs lg:text-sm text-white/60 leading-relaxed">
                        {feat.detail}
                      </p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
