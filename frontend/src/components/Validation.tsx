const BENCHMARK_URL = "https://github.com/raghav-shell/VisionX/blob/main/benchmarks/latest.md";

// Copied from benchmarks/latest.md. Change these only when that file changes.
const CAUGHT = [
  { name: "Targeted label flip", id: "label_flip_targeted" },
  { name: "Patch trigger poisoning", id: "patch_poison" },
  { name: "Model swap", id: "model_swap" },
  { name: "Modified weights", id: "modified_weights" },
  { name: "Ledger tampering", id: "ledger_tamper" },
  { name: "Illumination drift", id: "drift_illumination" },
];

const REST = [
  { name: "Duplicate flood", id: "duplicate_flood", s: "bad", res: "Missed" },
  { name: "Semantic shift", id: "semantic_shift", s: "bad", res: "Missed" },
  { name: "Systematic mislabel", id: "systematic_mislabel", s: "held", res: "Excluded" },
  { name: "Clean baseline, 400 samples", id: "clean_baseline", s: "none", res: "2 alerts" },
];

export default function Validation() {
  return (
    <section id="proof" className="lx-section" aria-labelledby="lx-proof-title">
      <div className="lx-shell">
        <div className="lx-head">
          <p className="lx-eyebrow">
            <span>
              <span className="n">03</span> · Proof
            </span>
          </p>
          <h2 id="lx-proof-title" className="lx-h2">
            <span>Ten planted scenarios, measured.</span> <b>The misses are in the table.</b>
          </h2>
          <p className="lx-lede">
            Attack Lab builds each scenario from a fixed seed, so anyone can rerun it. The numbers here are copied
            from <code>benchmarks/latest.md</code> in the repository.
          </p>
        </div>

        <ul className="lx-stats lx-gap">
          <li>
            <small>Attacks caught</small>
            <b>6 of 8</b>
            <p>eligible attack scenarios showed the signal they were built to trigger.</p>
          </li>
          <li>
            <small>Clean control</small>
            <b>2 on 400</b>
            <p>material alerts on clean samples, 0.005 per sample. This is not a per-sample false-positive rate.</p>
          </li>
          <li>
            <small>Left out</small>
            <b>1</b>
            <p>scenario failed its own fitness gate before scoring, so it is not counted either way.</p>
          </li>
        </ul>

        <div className="lx-runs lx-gap">
          <div>
            <h3>Caught · 6</h3>
            <ul>
              {CAUGHT.map((run) => (
                <li key={run.id}>
                  <span className="lx-sq" data-s="ok" aria-hidden="true" />
                  <span className="nm">
                    {run.name}
                    <small>{run.id}</small>
                  </span>
                  <span className="res" data-s="ok">
                    Caught
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3>Missed, excluded and the clean control · 4</h3>
            <ul>
              {REST.map((run) => (
                <li key={run.id}>
                  <span className="lx-sq" data-s={run.s} aria-hidden="true" />
                  <span className="nm">
                    {run.name}
                    <small>{run.id}</small>
                  </span>
                  <span className="res" data-s={run.s}>
                    {run.res}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="lx-proof-foot">
          <p className="lx-note">
            One clean control does not generalise across attack families. AUROC is not estimated: the run had no
            compatible labelled scores.
          </p>
          <a className="lx-link" href={BENCHMARK_URL} target="_blank" rel="noopener noreferrer">
            Read the benchmark <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    </section>
  );
}
