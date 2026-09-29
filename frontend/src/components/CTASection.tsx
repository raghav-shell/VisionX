import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";

export default function CTASection() {
  return (
    <section id="get-started" className="relative isolate min-h-[620px] overflow-hidden border-t border-white/10 bg-black py-28 lg:flex lg:items-center lg:py-40">
      <img
        src="/images/bridge.png"
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute -right-[24%] bottom-0 -z-10 h-[62%] w-[125%] object-contain object-bottom opacity-55 md:-right-[12%] md:h-[85%] md:w-[95%] lg:-right-[8%] lg:h-full lg:w-[72%] lg:opacity-90"
      />
      <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-r from-black via-black/80 to-transparent" />
      <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-t from-black via-transparent to-black/30" />

      <div className="relative mx-auto w-full max-w-[1400px] px-6 lg:px-12">
        <div className="max-w-2xl">
          <span className="mb-7 inline-flex items-center gap-3 font-mono text-sm uppercase tracking-wider text-[#eca8d6]">
            <span className="h-px w-12 bg-[#eca8d6]" />
            Smart India Hackathon 2026 · SIH26228
          </span>
          <h2 className="font-display text-5xl font-bold leading-[0.92] tracking-tight text-white md:text-7xl lg:text-[105px]">
            Make vision<br />
            <span className="text-white/45">verifiable.</span>
          </h2>
          <p className="mt-8 max-w-xl text-base leading-relaxed text-white/65 md:text-lg">
            Explore the VisionX demo workspace, inspect scanner scenarios, and trace decisions
            from their inputs to evidence and provenance records.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-3">
            <Link
              href="/workspace"
              className="inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-black transition-colors hover:bg-[#f7d3eb]"
            >
              Open demo workspace
              <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href="https://github.com/raghav-shell/VisionX"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-black/40 px-6 py-3 text-sm font-medium text-white transition-colors hover:border-white/60 hover:bg-white/10"
            >
              View source
              <ArrowUpRight className="h-4 w-4" />
            </a>
          </div>
          <p className="mt-7 font-mono text-xs uppercase tracking-wider text-white/40">
            Dataset integrity · Model assurance · Inference provenance
          </p>
        </div>
      </div>
    </section>
  );
}
