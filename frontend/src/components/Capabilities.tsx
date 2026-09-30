const LAYERS = [
  {
    n: "01",
    name: "Data integrity",
    looks:
      "Duplicates, label flips, one contributor mislabelling a class, box geometry, metadata, out-of-distribution images and trigger-like patches.",
    get: "The affected samples as a contact sheet, per-contributor counts and confusion matrices.",
  },
  {
    n: "02",
    name: "Model integrity",
    looks:
      "Whether the candidate is the model you approved: architecture and weight fingerprints, behaviour probes, and backdoor indicators when the model gives enough access.",
    get: "Digest comparisons, probe results, and a list of checks that needed access you did not give.",
  },
  {
    n: "03",
    name: "Inference provenance",
    looks: "Ed25519 signatures on every ledger record, the hash chain that orders them, and Merkle checkpoints.",
    get: "Signature, chain and checkpoint results you can rerun offline. Catching a cut-off tail needs an external anchor.",
  },
  {
    n: "04",
    name: "Operational drift",
    looks: "New batches against a trusted reference, using KS, PSI and Wasserstein statistics.",
    get: "Which features moved and by how much. A shift is a reason to look, not proof of an attack.",
  },
  {
    n: "05",
    name: "Human governance",
    looks: "Disposition requests, reviewer roles and the reasons people give.",
    get: "A signed audit trail. An analyst cannot approve their own request.",
  },
];

const STATES = [
  { s: "ok", name: "ASSESSED", d: "Ran with everything it needed." },
  { s: "half", name: "PARTIALLY_ASSESSED", d: "Ran, with its limits written down." },
  { s: "none", name: "NOT_ASSESSED", d: "An input or access it needs was missing." },
  { s: "bad", name: "FAILED_TO_EXECUTE", d: "Tried to run and hit an error." },
  { s: "dash", name: "UNSUPPORTED", d: "No claim is made for this attack class." },
];

export default function Capabilities() {
  return (
    <section id="checks" className="lx-section" aria-labelledby="lx-checks-title">
      <div className="lx-shell">
        <div className="lx-head">
          <p className="lx-eyebrow">
            <span>
              <span className="n">02</span> · What it checks
            </span>
          </p>
          <h2 id="lx-checks-title" className="lx-h2">
            <span>23 detectors in five layers.</span> <b>Each one says what it could not see.</b>
          </h2>
          <p className="lx-lede">
            A detector only runs when it has the inputs and access it needs. When it can&apos;t, the report says so
            and says why.
          </p>
        </div>

        <div className="lx-gap">
          <div className="lx-layers-hd" aria-hidden="true">
            <span>Layer</span>
            <span>What it looks at</span>
            <span>What you get</span>
          </div>
          <ol className="lx-layers">
            {LAYERS.map((layer) => (
              <li key={layer.n} className="lx-layer">
                <div className="name">
                  <span className="n">{layer.n}</span>
                  <h3>{layer.name}</h3>
                </div>
                <div>
                  <span className="k">What it looks at</span>
                  <p>{layer.looks}</p>
                </div>
                <div>
                  <span className="k">What you get</span>
                  <p className="get">{layer.get}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="lx-cov lx-gap">
          <div>
            <p className="lx-eyebrow">
              <span>Coverage</span>
            </p>
            <h3>A missing check is never shown as a pass.</h3>
          </div>
          <ul className="lx-states">
            {STATES.map((state) => (
              <li key={state.name}>
                <span className="s">
                  <span className="lx-sq" data-s={state.s} aria-hidden="true" />
                  {state.name}
                </span>
                <p className="d">{state.d}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
