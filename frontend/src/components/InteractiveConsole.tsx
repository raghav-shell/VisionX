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
  const timelineRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const shellRefs = useRef<(HTMLDivElement | null)[]>([]);
  const windowRefs = useRef<(HTMLDivElement | null)[]>([]);
  const frameRef = useRef<number | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  useEffect(() => {
    const updateReveal = () => {
      frameRef.current = null;
      const viewportHeight = window.innerHeight;
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      shellRefs.current.forEach((shell, index) => {
        const window = windowRefs.current[index];
        if (!shell || !window) return;
        if (reducedMotion) {
          window.style.opacity = "1";
          window.style.transform = "none";
          return;
        }

        const top = shell.getBoundingClientRect().top;
        const progress = Math.min(Math.max((viewportHeight * 0.9 - top) / (viewportHeight * 0.48), 0), 1);
        const eased = progress * progress * (3 - 2 * progress);
        window.style.opacity = String(0.12 + eased * 0.88);
        window.style.transform = `translate3d(0, ${(1 - eased) * 56}px, 0)`;
      });

      const timeline = timelineRef.current;
      if (timeline && progressRef.current) {
        const bounds = timeline.getBoundingClientRect();
        const progress = Math.min(Math.max((viewportHeight * 0.55 - bounds.top) / bounds.height, 0), 1);
        progressRef.current.style.transform = `scaleY(${progress})`;
      }
    };

    const requestUpdate = () => {
      if (frameRef.current === null) frameRef.current = requestAnimationFrame(updateReveal);
    };

    window.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);
    updateReveal();
    return () => {
      window.removeEventListener("scroll", requestUpdate);
      window.removeEventListener("resize", requestUpdate);
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
    <section id="console" className="relative overflow-clip border-t border-white/10 bg-[#020203] py-28 text-white lg:py-36">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <div className="mx-auto mb-20 max-w-2xl text-center lg:mb-28">
          <span className="mb-4 inline-flex items-center justify-center gap-3 font-mono text-sm uppercase tracking-wider text-white/50">
            <span className="h-px w-8 bg-[#eca8d6]" />
            Interactive instrument
            <span className="h-px w-8 bg-[#eca8d6]" />
          </span>
          <h2 className="mb-4 font-display text-4xl font-bold tracking-tight md:text-6xl">
            Explore the CLI workflow
          </h2>
          <p className="text-sm text-white/60 lg:text-base">
            Follow four illustrative excerpts: scan assets, compare drift, verify a ledger,
            and inspect coverage. Copy the commands to use with your own local files.
          </p>
        </div>
      </div>

      <div ref={timelineRef} className="relative mx-auto max-w-[1180px] px-6 lg:px-0">
        <div aria-hidden="true" className="absolute bottom-0 left-[32px] top-0 hidden w-px bg-white/10 lg:block">
          <div ref={progressRef} className="h-full w-full origin-top scale-y-0 bg-[#eca8d6]" />
        </div>

        {scenarios.map((scenario, index) => (
          <article
            key={scenario.label}
            aria-labelledby={`console-step-${index}`}
            className="relative py-24 lg:grid lg:grid-cols-[88px_minmax(0,1fr)] lg:gap-8 lg:py-32"
          >
            <div aria-hidden="true" className="hidden items-start gap-4 pt-2 lg:flex">
              <span className="relative z-10 ml-[26px] mt-0.5 h-3.5 w-3.5 shrink-0 rounded-full border border-[#eca8d6]/70 bg-[#160e15]" />
              <span className="font-mono text-xs text-[#eca8d6]">{String(index + 1).padStart(2, "0")}</span>
            </div>

            <div ref={(node) => { shellRefs.current[index] = node; }} className="min-w-0">
              <div ref={(node) => { windowRefs.current[index] = node; }} className="will-change-[transform,opacity]">
                <div className="mb-5 flex items-center justify-between gap-4 font-mono text-[11px] uppercase tracking-wider text-white/50 md:text-xs">
                  <h3 id={`console-step-${index}`} className="font-normal text-[#eca8d6]">
                    <span className="lg:hidden">{String(index + 1).padStart(2, "0")} / 04</span>
                    <span className="hidden lg:inline">Example {String(index + 1).padStart(2, "0")}</span>
                  </h3>
                  <span>{scenario.label}</span>
                </div>

                <div className="overflow-hidden rounded-xl border border-white/20 bg-[#050506] shadow-[0_24px_70px_rgba(0,0,0,0.55)]">
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
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
