import { ArrowUpRight, Fingerprint, FlaskConical, ScanSearch } from "lucide-react";

const checks = [
  {
    icon: FlaskConical,
    number: "01",
    title: "Clean and attacked corpora",
    description:
      "Scientific tests check detector behavior on both clean samples and planted attacks, including false alarms and contributor attribution.",
    path: "tests/scientific/",
    href: "https://github.com/raghav-shell/VisionX/tree/main/tests/scientific",
  },
  {
    icon: ScanSearch,
    number: "02",
    title: "Evidence for every finding",
    description:
      "Findings carry verifiable evidence or an explicit reason why evidence is unavailable. Coverage states disclose checks that could not run.",
    path: "tests/scientific/test_data_detectors.py",
    href: "https://github.com/raghav-shell/VisionX/blob/main/tests/scientific/test_data_detectors.py",
  },
  {
    icon: Fingerprint,
    number: "03",
    title: "Tamper checks",
    description:
      "Security tests exercise record edits, ledger attacks, and report evidence verification across the provenance workflow.",
    path: "tests/security/",
    href: "https://github.com/raghav-shell/VisionX/tree/main/tests/security",
  },
];

export default function Validation() {
  return (
    <section id="validation" className="relative overflow-hidden border-t border-white/10 bg-[#050506] py-28 lg:py-36">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <div className="mb-16 flex flex-col gap-8 lg:mb-20 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span className="mb-7 inline-flex items-center gap-3 font-mono text-sm uppercase tracking-wider text-white/50">
              <span className="h-px w-12 bg-[#eca8d6]" />
              Hackathon validation
            </span>
            <h2 className="font-display text-5xl font-bold leading-[0.92] tracking-tight text-white md:text-7xl lg:text-[105px]">
              Evidence you<br />
              <span className="text-white/35">can inspect.</span>
            </h2>
          </div>
          <p className="max-w-md text-base leading-relaxed text-white/60 lg:pb-2 lg:text-lg">
            VisionX reports what it assessed, what it could only partially assess, and the evidence
            behind each finding. The test suite exercises those claims on clean and adversarial cases.
          </p>
        </div>

        <div className="grid overflow-hidden border border-white/15 bg-black lg:grid-cols-[1.15fr_0.85fr]">
          <div className="relative min-h-[360px] overflow-hidden border-b border-white/15 p-8 md:p-12 lg:border-b-0 lg:border-r lg:p-14">
            <div className="absolute -right-24 -top-24 h-80 w-80 rounded-full bg-[#eca8d6]/10 blur-[100px]" />
            <div className="relative flex h-full flex-col justify-between gap-20">
              <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.2em] text-[#eca8d6]">
                <span className="h-2 w-2 rounded-full bg-[#eca8d6]" />
                Coverage is explicit
              </div>
              <div>
                <p className="max-w-2xl font-display text-3xl font-medium leading-tight text-white md:text-4xl lg:text-5xl">
                  Every conclusion states its coverage and shows its evidence or limits.
                </p>
                <a
                  href="https://github.com/raghav-shell/VisionX"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-9 inline-flex items-center gap-2 border-b border-[#eca8d6]/50 pb-1 text-sm font-medium text-[#eca8d6] transition-colors hover:border-[#eca8d6] hover:text-white"
                >
                  Inspect the project source
                  <ArrowUpRight className="h-4 w-4" />
                </a>
              </div>
            </div>
          </div>
          <div className="flex flex-col justify-center divide-y divide-white/10 p-8 md:p-12 lg:p-14">
            {[
              ["ASSESSED", "Check ran with required inputs"],
              ["PARTIALLY ASSESSED", "Limits are stated in the report"],
              ["NOT ASSESSED", "Missing prerequisites are visible"],
              ["UNSUPPORTED", "Attack class is declared explicitly"],
            ].map(([status, description]) => (
              <div key={status} className="flex items-start gap-4 py-5 first:pt-0 last:pb-0">
                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[#eca8d6]" />
                <div>
                  <span className="block font-mono text-xs tracking-wider text-white">{status}</span>
                  <span className="mt-1 block text-sm text-white/45">{description}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-5 grid gap-5 md:grid-cols-3">
          {checks.map((check) => {
            const Icon = check.icon;
            return (
              <div key={check.title} className="flex flex-col border border-white/10 bg-[#09090b] p-7 lg:p-8">
                <div className="mb-10 flex items-center justify-between">
                  <span className="flex h-11 w-11 items-center justify-center border border-white/20 text-[#eca8d6]">
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="font-mono text-xs text-white/35">{check.number}</span>
                </div>
                <h3 className="mb-3 font-display text-xl font-semibold text-white">{check.title}</h3>
                <p className="mb-8 flex-1 text-sm leading-relaxed text-white/55">{check.description}</p>
                <a href={check.href} target="_blank" rel="noopener noreferrer" className="flex items-center justify-between gap-2 break-all border-t border-white/10 pt-4 font-mono text-[11px] text-white/40 transition-colors hover:text-[#eca8d6]">
                  {check.path}
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0" />
                </a>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
