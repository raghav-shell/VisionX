"use client";

import React, { useEffect, useRef } from "react";

/*
 * How it works, told with the recorded demo run. The tree is the pipeline:
 * four contributors are its branches and the dataset is its trunk. When the
 * figure is reached, one scan pass checks each branch, Charlie's branch locks,
 * the finding traces out to the readout, and the readout settles REVIEW and
 * then the second signature. Every figure below comes from that run.
 *
 * The whole sequence is CSS on one clock (globals.css, "the contributor tree"):
 * each piece carries its start time as --t. This component only arms it and
 * starts it. Without JavaScript, under reduced motion, or when the figure is
 * already on screen at load, nothing is armed and the finished frame shows.
 */

type Pin = {
  id: string;
  x: number;
  y: number;
  t: number;
  kind?: "data" | "flag";
  dir?: "up" | "down" | "left";
  align?: "start" | "end";
  len?: number;
  name?: string;
  note?: string;
};

// Positions are percentages of the tree image; t is ms after the run starts.
// The scan climbs from 96% to 4% of the height between 400 and 2200 ms, so a
// branch is checked at the moment the line crosses it.
const PINS: Pin[] = [
  { id: "data", kind: "data", x: 35, y: 70, t: 100, dir: "left", len: 20, name: "Dataset", note: "400 images" },
  { id: "alpha", x: 21, y: 43, t: 1440, dir: "down", align: "start", name: "Alpha", note: "No pattern" },
  { id: "delta", x: 86, y: 30, t: 1690, dir: "down", align: "end", name: "Delta", note: "No pattern" },
  { id: "bravo", x: 38, y: 15, t: 1985, dir: "up", align: "end", len: 10, name: "Bravo", note: "No pattern" },
  { id: "charlie", kind: "flag", x: 62.75, y: 16.1, t: 2350 },
];

const STEPS = [
  {
    n: "01",
    t: 100,
    title: "Import",
    body: "Load a dataset, a candidate model or a signed inference ledger. Every sample keeps the name of the contributor who sent it.",
    run: "400 images from Alpha, Bravo, Charlie and Delta",
  },
  {
    n: "02",
    t: 400,
    title: "Run the detectors",
    body: "Pick a profile. VisionX works out which of its 23 detectors your inputs allow, then runs them on this machine.",
    run: "Labels checked against image content, per contributor",
  },
  {
    n: "03",
    t: 2350,
    title: "Read the evidence",
    body: "A finding opens to its detector, the samples it hit and the evidence, with the limits of the check written out. Coverage lists what did not run.",
    run: "Charlie: 5 of 33. Everyone else: 0 of 46",
  },
  {
    n: "04",
    t: 3850,
    title: "Sign it off",
    body: "The policy proposes ACCEPT, REVIEW or QUARANTINE. Changing that takes a request and a second person's approval.",
    run: "REVIEW, then analyst01 asks and approver01 decides",
  },
];

const at = (ms: number) => ({ "--t": `${ms}ms` }) as React.CSSProperties;

export default function Process() {
  const root = useRef<HTMLElement>(null);
  const tree = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = root.current;
    const fig = tree.current;
    if (!el || !fig) return;
    if (!window.matchMedia("(prefers-reduced-motion: no-preference)").matches) return;
    if (typeof IntersectionObserver === "undefined") return;
    el.dataset.motion = "";
    const box = fig.getBoundingClientRect();
    if (box.top < window.innerHeight && box.bottom > 0) return;
    el.dataset.play = "armed";
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          el.dataset.play = "on";
          io.disconnect();
        }
      },
      { threshold: 0.45 },
    );
    io.observe(fig);
    return () => io.disconnect();
  }, []);

  const replay = () => {
    const el = root.current;
    if (!el) return;
    el.dataset.play = "armed";
    void el.offsetWidth; // let the armed frame apply so the animations start over
    el.dataset.play = "on";
  };

  return (
    <section ref={root} id="demo" className="lx-section" aria-labelledby="lx-demo-title">
      <div className="lx-shell">
        <div className="lx-head">
          <p className="lx-eyebrow">
            <span>
              <span className="n">01</span> · How it works
            </span>
          </p>
          <h2 id="lx-demo-title" className="lx-h2">
            <span>Charlie relabelled armoured vehicles as civilian.</span> <b>VisionX caught it.</b>
          </h2>
          <p className="lx-lede">
            This is the recorded demo run, Attack Lab&apos;s targeted label flip: 400 images from four contributors,
            about 75 seconds on a laptop CPU. Anything you import goes through the same four steps.
          </p>
        </div>

        <div className="lx-demo-grid">
          <ol className="lx-steps">
            {STEPS.map((step) => (
              <li key={step.n} className="lx-step" style={at(step.t)}>
                <span className="k">
                  <span className="mk" aria-hidden="true" />
                  {step.n}
                </span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                  <p className="run">
                    <span>Run ›</span>
                    {step.run}
                  </p>
                </div>
              </li>
            ))}
          </ol>

          <figure className="lx-stage">
            <div ref={tree} className="lx-tree">
              <img
                src="/images/tree-mono.webp"
                alt="A bonsai tree drawn as the dataset. Its four branches are the contributors Alpha, Bravo, Charlie and Delta. Alpha, Bravo and Delta are marked as showing no pattern; Charlie's branch is flagged: 5 of 33 relabelled, q 3.8e-04."
                width={1100}
                height={1178}
                loading="lazy"
                decoding="async"
              />

              {PINS.map((pin) => (
                <div
                  key={pin.id}
                  className="lx-pin"
                  data-kind={pin.kind}
                  data-dir={pin.dir}
                  data-align={pin.align}
                  aria-hidden="true"
                  style={{
                    ...at(pin.t),
                    ["--x" as string]: `${pin.x}%`,
                    ["--y" as string]: `${pin.y}%`,
                    ...(pin.len ? { ["--len" as string]: `${pin.len}px` } : {}),
                  }}
                >
                  <i className="dot" />
                  {pin.name && (
                    <>
                      <i className="lead" />
                      <span className="tag">
                        <b>{pin.name}</b>
                        <span className="st">
                          <em>{pin.note}</em>
                          {pin.kind !== "data" && <i className="w">Queued</i>}
                        </span>
                      </span>
                    </>
                  )}
                </div>
              ))}

              <div className="lx-reticle" style={at(2350)} aria-hidden="true">
                <i />
                <i />
                <i />
                <i />
              </div>
              <span className="lx-ctag" style={at(2350)} aria-hidden="true">
                Charlie
              </span>
              <i className="lx-flag-lead" style={at(2650)} aria-hidden="true" />
              <p className="lx-flag" style={at(3070)} aria-hidden="true">
                <b>CHARLIE</b>
                <span>5/33 RELABELLED</span>
                <span>q 3.8e-04</span>
              </p>

              <div className="lx-scanlayer" aria-hidden="true">
                <div className="lx-scan">
                  <i />
                  <span>DATA CHECKS RUNNING</span>
                </div>
              </div>
            </div>

            <figcaption className="lx-stage-cap">
              <span className="lx-note">Recorded run · targeted label flip · profile selftest · about 75 s, laptop CPU</span>
              <button type="button" className="lx-replay" onClick={replay}>
                Replay <span aria-hidden="true">↻</span>
              </button>
            </figcaption>
          </figure>

          <div className="lx-readout">
            <p className="hd">
              <span>Finding</span>
              <span>F-7EC600D0C8</span>
            </p>
            <div className="lx-findwrap">
              <p className="lx-wait" style={at(3250)} aria-hidden="true">
                Detectors running · no findings yet
              </p>
              <div className="lx-find" style={at(3250)}>
                <p className="who">CHARLIE · MEDIUM</p>
                <p className="t">
                  Charlie systematically labels <code>armoured_vehicle</code> content as <code>civilian_vehicle</code>
                </p>
                <p className="b">
                  <mark className="lx-mark">5 of 33</mark> of Charlie&apos;s <code>civilian_vehicle</code> labels are on
                  images the model reads as armoured vehicles. Other contributors: 0 of 46.
                </p>
                <dl>
                  <dt>Detector</dt>
                  <dd>data.systematic_mislabel</dd>
                  <dt>Test</dt>
                  <dd>binomial, q = 3.8e-04</dd>
                  <dt>Evidence</dt>
                  <dd>contact sheet, confusion matrix, test statistics</dd>
                </dl>
              </div>
            </div>

            <ol className="lx-flow">
              <li style={at(3850)}>
                <span className="lx-sq" data-s="held" />
                <div className="row">
                  <span className="k">Policy</span>
                  <span className="lx-disp">REVIEW</span>
                </div>
                <p>Proposed from the evidence. Nobody has signed anything yet.</p>
              </li>
              <li style={at(4250)}>
                <span className="lx-sq" />
                <div className="row">
                  <span className="k">Request</span>
                  <span className="v">analyst01</span>
                </div>
                <p>Asks to change the disposition and writes down why.</p>
              </li>
              <li style={at(4650)}>
                <span className="lx-sq" data-s="ok" />
                <div className="row">
                  <span className="k">Decision</span>
                  <span className="v">approver01</span>
                </div>
                <p>A second person approves or rejects. Both steps go into the signed audit trail.</p>
              </li>
            </ol>
            <p className="lx-note" style={at(4950)}>
              If analyst01 tries to approve their own request, the backend refuses and logs the attempt.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
