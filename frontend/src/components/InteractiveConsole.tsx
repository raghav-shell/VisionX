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
      setActiveIndex(Math.min(Math.floor(progress * scenarios.length), scenarios.length - 1));
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

      <div ref={trackRef} className="relative h-[380svh]">
        <div className="sticky top-[72px] flex h-[calc(100svh-72px)] items-center py-4 lg:top-[84px] lg:h-[calc(100svh-84px)]">
          <div className="mx-auto w-full max-w-[1400px] px-6 lg:px-12">
            <div className="mx-auto max-w-4xl">
              <div className="mb-5 flex items-center justify-between gap-4 font-mono text-[11px] uppercase tracking-wider text-white/45 md:text-xs">
                <span>CLI walkthrough</span>
                <span aria-live="polite">{String(activeIndex + 1).padStart(2, "0")} / 04</span>
              </div>

              <div key={activeIndex} className="console-window-enter overflow-hidden rounded-xl border border-white/25 bg-black/95 shadow-2xl">
                <div className="flex items-center justify-between gap-3 border-b border-white/10 bg-white/[0.03] px-4 py-3.5 md:px-5">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="h-3 w-3 shrink-0 rounded-full bg-[#ff5f56]/80" />
                    <span className="h-3 w-3 shrink-0 rounded-full bg-[#ffbd2e]/80" />
                    <span className="h-3 w-3 shrink-0 rounded-full bg-[#27c93f]/80" />
                    <span className="ml-2 truncate font-mono text-[11px] text-white/45 md:ml-3 md:text-xs">
                      visionsentinel — {scenarios[activeIndex].label}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => copyCommand(activeIndex)}
                    className="inline-flex shrink-0 items-center gap-1.5 font-mono text-[11px] text-white/60 transition-colors hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#eca8d6] md:text-xs"
                    aria-label={`Copy ${scenarios[activeIndex].label} command`}
                  >
                    {copiedIndex === activeIndex ? <Check className="h-3.5 w-3.5 text-[#91dcbc]" /> : <Copy className="h-3.5 w-3.5" />}
                    <span className="hidden sm:inline">{copiedIndex === activeIndex ? "Copied" : "Copy command"}</span>
                  </button>
                </div>
                <div className="flex items-start gap-3 border-b border-white/10 px-4 py-4 font-mono text-xs md:items-center md:px-6 md:text-sm">
                  <span className="text-white/40">$</span>
                  <span className="select-all break-all text-white md:whitespace-nowrap">{scenarios[activeIndex].command}</span>
                </div>
                <pre className="max-h-[48svh] overflow-y-auto whitespace-pre-wrap break-words p-4 font-mono text-[11px] leading-relaxed text-white/80 selection:bg-[#eca8d6] selection:text-black md:max-h-[440px] md:p-6 md:text-sm">
                  {scenarios[activeIndex].output}
                </pre>
              </div>

              <div className="mt-6 flex items-center gap-3" aria-label={`Step ${activeIndex + 1} of four: ${scenarios[activeIndex].label}`}>
                {scenarios.map((scenario, index) => (
                  <div key={scenario.label} className="h-1 flex-1 overflow-hidden rounded-full bg-white/10" aria-hidden="true">
                    <div className={`h-full origin-left rounded-full bg-[#eca8d6] transition-transform duration-500 motion-reduce:transition-none ${index <= activeIndex ? "scale-x-100" : "scale-x-0"}`} />
                  </div>
                ))}
              </div>
              <p className="mt-4 text-center font-mono text-[11px] uppercase tracking-widest text-white/35">
                Scroll to explore the next command
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
