"use client";

import React, { useEffect, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";

const scenarios = [
  {
    label: "Full scan & plan",
    command: "visionsentinel scan --dataset ./data --model ./model.onnx --out ./reports",
    output: `[EXAMPLE] Illustration of a local assessment, not a live scan.

CAPABILITIES
  Dataset images: available
  Model gradients: availability depends on the model

DETECTORS
  Planned checks report their final state and reasons.
  Findings link to evidence in the exported report.

COVERAGE
  Each attack class is assessed, partially assessed, not assessed,
  failed to execute, or explicitly unsupported.

OUTPUT
  report.json · report.html · coverage.md · manifest.json`,
  },
  {
    label: "Distribution drift",
    command: "visionsentinel drift --reference ./baseline --incoming ./incoming --out ./reports",
    output: `[EXAMPLE] Compare incoming images with a reference dataset.

  The report lists evaluated visual axes and their differences.
  It identifies statistically supported shifts and known limits.
  A shift prompts investigation; it does not prove an attack.`,
  },
  {
    label: "Offline verification",
    command: "visionsentinel verify ./ledger.jsonl --trust-root ./trust.json --anchor ./anchors.jsonl",
    output: `[EXAMPLE] Verify a signed inference ledger offline.

  Check canonical records and Ed25519 signatures.
  Recompute Merkle checkpoints against the ledger history.
  Compare with external anchors when provided.

  Without an external anchor, tail truncation cannot be assessed.`,
  },
  {
    label: "Coverage & limits",
    command: "visionsentinel detectors",
    output: `[EXAMPLE] Inspect registered checks before a scan.

  See required inputs, supported attack classes, and limitations.
  The scan report records what ran and what could not run.
  Unsupported attack classes are declared rather than hidden.`,
  },
] as const;

export default function InteractiveConsole() {
  const trackRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);
  const progressRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  useEffect(() => {
    const updateStep = () => {
      frameRef.current = null;
      const track = trackRef.current;
      if (!track) return;
      const bounds = track.getBoundingClientRect();
      const scrollable = Math.max(bounds.height - window.innerHeight, 1);
      const progress = Math.min(Math.max(-bounds.top / scrollable, 0), 1);
      const chapter = Math.min(progress * scenarios.length, scenarios.length - 0.001);
      const whole = Math.floor(chapter);
      const transition = Math.min(Math.max((chapter - whole - 0.16) / 0.68, 0), 1);
      const eased = transition * transition * (3 - 2 * transition);
      const position = Math.min(whole + eased, scenarios.length - 1);
      const focused = Math.round(position);
      const travel = Math.min(window.innerHeight * 0.35, 320);
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      cardRefs.current.forEach((card, index) => {
        if (!card) return;
        const distance = index - position;
        const separation = Math.min(Math.abs(distance), 1.5);
        card.style.transform = reducedMotion
          ? "translate3d(0, -50%, 0)"
          : `translate3d(0, calc(-50% + ${distance * travel}px), 0) scale(${1 - separation * 0.045})`;
        card.style.opacity = reducedMotion
          ? String(index === focused ? 1 : 0)
          : String(Math.min(1, Math.max(0, (1 - Math.abs(distance)) * 3)));
        card.style.pointerEvents = index === focused ? "auto" : "none";
      });

      if (progressRef.current) progressRef.current.style.transform = `scaleX(${progress})`;
      setActiveIndex((current) => (current === focused ? current : focused));
    };

    const requestStep = () => {
      if (frameRef.current === null) frameRef.current = requestAnimationFrame(updateStep);
    };

    window.addEventListener("scroll", requestStep, { passive: true });
    window.addEventListener("resize", requestStep);
    updateStep();
    return () => {
      window.removeEventListener("scroll", requestStep);
      window.removeEventListener("resize", requestStep);
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    };
  }, []);

  const copyCommand = async (index: number) => {
    try {
      await navigator.clipboard.writeText(scenarios[index].command);
      setCopiedIndex(index);
      window.setTimeout(() => setCopiedIndex((current) => (current === index ? null : current)), 2000);
    } catch {
      setCopiedIndex(null);
    }
  };

  return (
    <section id="console" className="relative overflow-clip border-t border-white/10 bg-[#020203] pt-28 text-white lg:pt-36">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <div className="mx-auto mb-12 max-w-2xl text-center lg:mb-20">
          <span className="mb-4 inline-flex items-center justify-center gap-3 font-mono text-sm uppercase tracking-wider text-white/50">
            <span className="h-px w-8 bg-[#eca8d6]" />
            Interactive instrument
            <span className="h-px w-8 bg-[#eca8d6]" />
          </span>
          <h2 className="mb-4 font-display text-4xl font-bold tracking-tight md:text-6xl">
            Explore the CLI workflow
          </h2>
          <p className="text-sm text-white/60 lg:text-base">
            Scroll through four illustrative excerpts: scan assets, compare drift, verify a ledger,
            and inspect coverage. Copy the commands to use with your own local files.
          </p>
        </div>
      </div>

      <div ref={trackRef} className="relative h-[440svh]">
        <div className="sticky top-[72px] flex h-[calc(100svh-72px)] items-center py-4 lg:top-[84px] lg:h-[calc(100svh-84px)]">
          <div className="mx-auto w-full max-w-[1400px] px-6 lg:px-12">
            <div className="mx-auto max-w-4xl">
              <div className="mb-5 flex items-center justify-between gap-4 font-mono text-[11px] uppercase tracking-wider text-white/45 md:text-xs">
                <span>CLI walkthrough</span>
                <span aria-live="polite">{String(activeIndex + 1).padStart(2, "0")} / 04</span>
              </div>

              <div className="relative h-[min(74svh,620px)] overflow-hidden rounded-2xl bg-[radial-gradient(ellipse_at_center,rgba(236,168,214,0.055),transparent_68%)]">
                {scenarios.map((scenario, index) => (
                  <div
                    key={scenario.label}
                    ref={(node) => { cardRefs.current[index] = node; }}
                    aria-hidden={index !== activeIndex}
                    className="absolute left-0 right-0 top-1/2 will-change-[transform,opacity] overflow-hidden rounded-xl border border-white/25 bg-[#050506] shadow-[0_28px_80px_rgba(0,0,0,0.7)]"
                    style={{
                      opacity: index === 0 ? 1 : 0,
                      transform: "translate3d(0, -50%, 0)",
                      pointerEvents: index === 0 ? "auto" : "none",
                    }}
                  >
                    <div className="flex items-center justify-between gap-3 border-b border-white/10 bg-white/[0.03] px-4 py-3.5 md:px-5">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="h-3 w-3 shrink-0 rounded-full bg-[#ff5f56]/80" />
                        <span className="h-3 w-3 shrink-0 rounded-full bg-[#ffbd2e]/80" />
                        <span className="h-3 w-3 shrink-0 rounded-full bg-[#27c93f]/80" />
                        <span className="ml-2 truncate font-mono text-[11px] text-white/45 md:ml-3 md:text-xs">
                          visionsentinel — {scenario.label}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => copyCommand(index)}
                        tabIndex={index === activeIndex ? 0 : -1}
                        className="inline-flex shrink-0 items-center gap-1.5 font-mono text-[11px] text-white/60 transition-colors hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#eca8d6] md:text-xs"
                        aria-label={`Copy ${scenario.label} command`}
                      >
                        {copiedIndex === index ? <Check className="h-3.5 w-3.5 text-[#91dcbc]" /> : <Copy className="h-3.5 w-3.5" />}
                        <span className="hidden sm:inline">{copiedIndex === index ? "Copied" : "Copy command"}</span>
                      </button>
                    </div>
                    <div className="flex items-start gap-3 border-b border-white/10 px-4 py-4 font-mono text-xs md:items-center md:px-6 md:text-sm">
                      <span className="text-white/40">$</span>
                      <span className="select-all break-all text-white md:whitespace-nowrap">{scenario.command}</span>
                    </div>
                    <pre className="whitespace-pre-wrap break-words p-4 font-mono text-[11px] leading-[1.35] text-white/80 selection:bg-[#eca8d6] selection:text-black md:p-6 md:text-sm md:leading-relaxed">
                      {scenario.output}
                    </pre>
                  </div>
                ))}
              </div>

              <div className="relative mt-5 h-px bg-white/15" role="progressbar" aria-valuemin={1} aria-valuemax={4} aria-valuenow={activeIndex + 1} aria-valuetext={scenarios[activeIndex].label}>
                <div ref={progressRef} className="absolute inset-y-0 left-0 w-full origin-left scale-x-0 bg-[#eca8d6]" />
                {scenarios.map((scenario, index) => (
                  <span
                    key={scenario.label}
                    aria-hidden="true"
                    className={`absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border transition-colors duration-200 ${index <= activeIndex ? "border-[#eca8d6] bg-[#eca8d6]" : "border-white/30 bg-[#09090b]"}`}
                    style={{ left: `${(index / scenarios.length) * 100}%` }}
                  />
                ))}
              </div>
              <p className="mt-4 text-center font-mono text-[11px] uppercase tracking-widest text-white/35">
                {activeIndex === scenarios.length - 1 ? "Continue to the next section" : "Scroll to explore the next command"}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
