import React from "react";

const signals = [
  {
    label: "Model assurance",
    title: "Trigger indicators",
    detail: "Review anomalous model responses and reconstructed triggers when the required model access is available.",
    footer: "Missing prerequisites stay visible",
    color: "text-[#eca8d6]",
  },
  {
    label: "Distribution drift",
    title: "Reference comparison",
    detail: "Compare incoming images with a trusted baseline across visual and, where available, model-derived features.",
    footer: "Interpret shifts before acting",
    color: "text-[#91dcbc]",
  },
  {
    label: "Provenance",
    title: "Record verification",
    detail: "Check signatures and Merkle history; supply an external anchor to detect truncated ledger tails.",
    footer: "Trust depends on supplied keys",
    color: "text-[#79cdf9]",
  },
];

export default function SignalMetrics() {
  return (
    <section id="signals" className="relative py-28 lg:py-36 bg-[#040406] text-white overflow-hidden border-t border-white/10">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="grid lg:grid-cols-12 gap-8 mb-20 lg:mb-32">
          <div className="lg:col-span-8">
            <span className="inline-flex items-center gap-2 px-3 py-1 mb-6 bg-[#eca8d6]/10 text-[#eca8d6] text-xs font-mono rounded-full border border-[#eca8d6]/20">
              ASSESSMENT SIGNALS
            </span>
            <h2 className="text-6xl md:text-7xl lg:text-[115px] font-display font-bold tracking-tight leading-[0.92] text-white">
              Signals with<br />
              <span className="text-white/40">context.</span>
            </h2>
          </div>
          <div className="lg:col-span-4 flex items-end">
            <p className="text-base lg:text-lg text-white/60 leading-relaxed">
              A score alone cannot establish trust. VisionX connects each signal to its inputs,
              evidence, access assumptions, and known limits.
            </p>
          </div>
        </div>

        <div className="relative w-full mb-12 rounded-2xl overflow-hidden border border-white/10 bg-black/60 shadow-2xl">
          <img src="/images/real-time-graph.png" alt="Illustration of multiple assessment signals" className="w-full h-auto object-cover select-none pointer-events-none" />
          <div className="absolute inset-0 bg-gradient-to-t from-[#040406] via-transparent to-transparent pointer-events-none" />
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {signals.map((signal) => (
            <div key={signal.title} className="bg-[#09090b] border border-white/15 p-8 lg:p-10 rounded-2xl flex flex-col justify-between hover:border-white/30 transition-all duration-300">
              <div>
                <span className={`text-xs font-mono uppercase tracking-wider ${signal.color}`}>{signal.label}</span>
                <h3 className="text-2xl lg:text-3xl font-display font-semibold text-white mt-6 mb-4">{signal.title}</h3>
                <p className="text-sm text-white/60 leading-relaxed">{signal.detail}</p>
              </div>
              <p className="text-xs font-mono text-white/40 mt-8 pt-4 border-t border-white/10">{signal.footer}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
