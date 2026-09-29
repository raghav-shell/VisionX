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
  const stageRefs = useRef<(HTMLElement | null)[]>([]);
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);
  const frameRef = useRef<number | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  useEffect(() => {
    const updateCards = () => {
      frameRef.current = null;
      const viewportCenter = window.innerHeight * 0.52;
      const radius = window.innerHeight * 0.72;
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      stageRefs.current.forEach((stage, index) => {
        const card = cardRefs.current[index];
        if (!stage || !card) return;
        if (reducedMotion) {
          card.style.transform = "none";
          card.style.opacity = "1";
          return;
        }

        const bounds = stage.getBoundingClientRect();
        const stageCenter = (bounds.top + bounds.bottom) / 2;
        const focus = Math.min(Math.max(1 - Math.abs(stageCenter - viewportCenter) / radius, 0), 1);
        const eased = focus * focus * (3 - 2 * focus);
        const direction = stageCenter > viewportCenter ? 1 : -1;
        card.style.transform = `translate3d(0, ${direction * (1 - eased) * 36}px, 0) scale(${0.78 + eased * 0.22})`;
        card.style.opacity = String(0.3 + eased * 0.7);
      });
    };

    const requestUpdate = () => {
      if (frameRef.current === null) frameRef.current = requestAnimationFrame(updateCards);
    };

    window.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);
    updateCards();
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
    <section id="console" className="relative overflow-clip border-t border-white/10 bg-[#020203] pt-28 text-white lg:pt-36">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <div className="mx-auto mb-8 max-w-2xl text-center lg:mb-12">
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

        {scenarios.map((scenario, index) => (
          <article
            key={scenario.label}
            ref={(node) => { stageRefs.current[index] = node; }}
            aria-labelledby={`console-step-${index}`}
            className="relative flex min-h-[95svh] items-center py-20 md:min-h-[105svh]"
          >
            <div
              ref={(node) => { cardRefs.current[index] = node; }}
              className="mx-auto w-full max-w-4xl origin-center will-change-[transform,opacity]"
            >
              <div className="mb-5 flex items-center justify-between gap-4 font-mono text-[11px] uppercase tracking-wider text-white/50 md:text-xs">
                <h3 id={`console-step-${index}`} className="font-normal text-[#eca8d6]">
                  {String(index + 1).padStart(2, "0")} / 04
                </h3>
                <span>{scenario.label}</span>
              </div>

              <div className="overflow-hidden rounded-xl border border-white/25 bg-[#050506] shadow-[0_28px_80px_rgba(0,0,0,0.7)]">
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
          </article>
        ))}
      </div>
    </section>
  );
}
