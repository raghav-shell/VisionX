"use client";

import React, { useState } from "react";

const ROWS = [
  {
    k: "On your machine",
    d: "Assessments, evidence and reports stay in a local workspace folder. A guard refuses non-local network destinations from Python, and a self-test checks it.",
  },
  {
    k: "Bounded model worker",
    d: "Untrusted models run in a separate worker that blocks sockets, new processes and file access. Linux adds a network namespace and resource limits; elsewhere the report says they were not applied.",
  },
  {
    k: "Signed ledger",
    d: "Inference records are Ed25519-signed, hash-chained and checkpointed in a Merkle tree. One command verifies them offline against your trust root.",
  },
  {
    k: "Portable report",
    d: "Every scan writes report.json, report.html, coverage.md and manifest.json with file digests. Pass a key and the manifest is signed too.",
  },
];

const COMMANDS = [
  {
    c: "Assess what you were handed",
    cmd: "visionsentinel scan --dataset ./data --model ./candidate.onnx --profile strict --out ./reports",
  },
  { c: "Verify a signed inference ledger", cmd: "visionsentinel verify ./ledger.jsonl --trust-root ./trust-root.json" },
  { c: "Check the offline guards", cmd: "visionsentinel selftest --airgap" },
];

export default function Security() {
  const [copied, setCopied] = useState<number | null>(null);

  const copy = async (index: number) => {
    try {
      await navigator.clipboard.writeText(COMMANDS[index].cmd);
      setCopied(index);
      window.setTimeout(() => setCopied((current) => (current === index ? null : current)), 1800);
    } catch {
      setCopied(null);
    }
  };

  return (
    <section id="offline" className="lx-section" aria-labelledby="lx-offline-title">
      <div className="lx-shell">
        <div className="lx-head">
          <p className="lx-eyebrow">
            <span>
              <span className="n">04</span> · Offline
            </span>
          </p>
          <h2 id="lx-offline-title" className="lx-h2">
            <span>It runs on the machine</span> <b>that holds the data.</b>
          </h2>
          <p className="lx-lede">
            No hosted service and no account. Install the dependencies once on a connected machine, then move it
            offline.
          </p>
        </div>

        <div className="lx-off lx-gap">
          <ul className="lx-rows">
            {ROWS.map((row) => (
              <li key={row.k}>
                <h3>{row.k}</h3>
                <p>{row.d}</p>
              </li>
            ))}
          </ul>

          <div className="lx-term">
            <div className="bar">
              <span>Terminal</span>
              <span>Python 3.12+</span>
            </div>
            <ol>
              {COMMANDS.map((item, index) => (
                <li key={item.cmd}>
                  <div className="c">
                    <span># {item.c}</span>
                    <button
                      type="button"
                      className="lx-copy"
                      data-done={copied === index ? "" : undefined}
                      onClick={() => copy(index)}
                      aria-label={`Copy: ${item.cmd}`}
                    >
                      {copied === index ? "Copied" : "Copy"}
                    </button>
                  </div>
                  <pre>
                    <span className="p">$ </span>
                    {item.cmd}
                  </pre>
                </li>
              ))}
              <li>
                <div className="c">
                  <span># What a scan leaves behind</span>
                </div>
                <pre className="o">
                  {"reports/\n  report.json    report.html\n  coverage.md    manifest.json"}
                </pre>
              </li>
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
