"use client";

import React, { useState, useEffect, useRef } from "react";

export default function Process() {
  const [activeStep, setActiveStep] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const sectionRef = useRef<HTMLElement>(null);

  const steps = [
    {
      number: "01",
      title: "Ingest",
      subtitle: "raw training datasets",
      description:
        "Stream training batches through sandboxed memory rings. Extract perceptual dHash fingerprints, detect train/val split leakage, and validate bounding box coordinate normalization in real time.",
      accent: "#eca8d6",
    },
    {
      number: "02",
      title: "Audit",
      subtitle: "weights & triggers",
      description:
        "Execute Neural Cleanse inverted trigger reconstruction across all target classes. Minimize L1 mask norm via optimization to uncover planted backdoor Trojans without requiring ground-truth poison labels.",
      accent: "#c597eb",
    },
    {
      number: "03",
      title: "Seal",
      subtitle: "immutable provenance",
      description:
        "Package verified model checkpoints into zero-copy VisionX-SEAL containers with RFC 8785 canonical JSON manifests, detached Ed25519 signatures, and append-only RFC 6962 Merkle ledger receipts.",
      accent: "#9bb2ff",
    },
  ];

  // IntersectionObserver for smooth entry reveal
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.15 }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  // Auto-advance tabs
  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % steps.length);
    }, 6000);
    return () => clearInterval(timer);
  }, [steps.length]);

  return (
    <section
      ref={sectionRef}
      id="process"
      className="relative py-32 lg:py-44 bg-[#030305] text-white overflow-hidden border-t border-white/[0.06]"
    >
      {/* Background ambient glow */}
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] rounded-full bg-[#eca8d6]/[0.03] blur-[140px] pointer-events-none" />

      <div className="relative z-10 max-w-[1400px] mx-auto px-6 lg:px-12">
        {/* Header Grid: Stacked Typography + Living Tree Visual */}
        <div className="grid lg:grid-cols-2 gap-8 lg:gap-16 items-end mb-20 lg:mb-28">
          {/* Left: Stacked Headings */}
          <div className="overflow-hidden pb-4 lg:pb-24">
            <div
              className={`transition-all duration-1000 ${
                isVisible ? "translate-x-0 opacity-100" : "-translate-x-12 opacity-0"
              }`}
            >
              <span className="inline-flex items-center gap-3 text-sm font-mono text-white/40 mb-8 uppercase tracking-widest">
                <span className="w-12 h-px bg-white/20" />
                Assurance Process
              </span>
            </div>

            <h2
              className={`text-6xl md:text-7xl lg:text-[120px] font-display font-bold tracking-tight leading-[0.88] transition-all duration-1000 delay-100 ${
                isVisible ? "translate-y-0 opacity-100" : "translate-y-16 opacity-0"
              }`}
            >
              <span className="block text-white">Ingest.</span>
              <span className="block text-white/35">Audit.</span>
              <span className="block text-white/15">Seal.</span>
            </h2>
          </div>

          {/* Right: Living Ethereal Bonsai Tree Graphic with Continuous Motion */}
          <div
            className={`relative h-[360px] lg:h-[600px] overflow-hidden transition-all duration-1000 delay-200 ${
              isVisible ? "translate-y-0 opacity-100" : "translate-y-16 opacity-0"
            }`}
          >
            {/* Ambient backlight glow pulse */}
            <div
              className="absolute bottom-6 right-1/4 w-80 h-80 rounded-full blur-[100px] pointer-events-none transition-all duration-700 animate-aura-pulse"
              style={{
                backgroundColor: steps[activeStep].accent + "26",
              }}
            />

            {/* Tree Image with Living Organic Breathing Float */}
            <img
              src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/tree-uAia6REvB137CQyHFCf0za3O6h2zKO.png"
              alt="Ethereal bonsai tree"
              aria-hidden="true"
              className="absolute bottom-0 left-0 w-full h-full object-contain object-bottom select-none pointer-events-none animate-tree-float"
            />

            {/* Gradient Scrim for seamless blend */}
            <div className="absolute inset-0 bg-gradient-to-r from-[#030305] via-transparent to-transparent pointer-events-none" />
          </div>
        </div>

        {/* 3 Step Interactive Tab Cards with animated progress bar */}
        <div className="grid lg:grid-cols-3 gap-6">
          {steps.map((step, idx) => {
            const isActive = activeStep === idx;
            return (
              <button
                key={step.number}
                type="button"
                onClick={() => setActiveStep(idx)}
                className={`relative text-left p-8 lg:p-12 border rounded-none transition-all duration-500 bg-black ${
                  isActive
                    ? "border-white/60 shadow-xl shadow-white/5"
                    : "border-white/15 hover:border-white/40"
                }`}
              >
                {/* Step Number + Progress Indicator */}
                <div className="flex items-center gap-4 mb-8">
                  <span
                    className={`text-4xl font-display font-bold transition-colors duration-300 ${
                      isActive ? "text-[#eca8d6]" : "text-white/20"
                    }`}
                  >
                    {step.number}
                  </span>
                  <div className="flex-1 h-px bg-white/10 overflow-hidden">
                    {isActive && (
                      <div className="h-full bg-[#eca8d6]/60 animate-step-progress" />
                    )}
                  </div>
                </div>

                {/* Step Title & Subtitle */}
                <h3 className="text-3xl lg:text-4xl font-display font-semibold mb-2 text-white">
                  {step.title}
                </h3>
                <span className="text-lg lg:text-xl text-white/40 font-display block mb-6 font-normal">
                  {step.subtitle}
                </span>

                {/* Description */}
                <p
                  className={`text-sm lg:text-base text-white/60 leading-relaxed transition-opacity duration-300 ${
                    isActive ? "opacity-100" : "opacity-50"
                  }`}
                >
                  {step.description}
                </p>

                {/* Active bottom neon accent line */}
                <div
                  className={`absolute bottom-0 left-0 right-0 h-1 bg-[#eca8d6] transition-transform duration-500 origin-left ${
                    isActive ? "scale-x-100" : "scale-x-0"
                  }`}
                />
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
