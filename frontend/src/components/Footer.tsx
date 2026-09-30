"use client";

import React from "react";
import Link from "next/link";
import VisionXLogo from "./VisionXLogo";

const REPO_URL = "https://github.com/raghav-shell/VisionX";

const LINKS = [
  { name: "Workspace", href: "/workspace", internal: true },
  { name: "GitHub", href: REPO_URL },
  { name: "Benchmark", href: `${REPO_URL}/blob/main/benchmarks/latest.md` },
  { name: "Handbook", href: `${REPO_URL}/tree/main/docs/handbook` },
];

export default function Footer() {
  return (
    <footer className="lx-footer">
      <div className="lx-shell">
        <div className="top">
          <div>
            <Link href="/" aria-label="VisionX home" className="lx-home">
              <VisionXLogo size={26} showText textClassName="text-[19px]" />
            </Link>
            <p>
              Offline integrity checks for computer-vision data, models and inference records. Built for Smart India
              Hackathon 2026, problem SIH26228: integrity assurance for data, models and inference outputs in
              multi-contributor pipelines.
            </p>
          </div>
          <nav aria-label="Footer">
            {LINKS.map((link) =>
              link.internal ? (
                <Link key={link.name} href={link.href}>
                  {link.name}
                </Link>
              ) : (
                <a key={link.name} href={link.href} target="_blank" rel="noopener noreferrer">
                  {link.name} <span aria-hidden="true">↗</span>
                </a>
              ),
            )}
          </nav>
        </div>
        <div className="bottom">
          <span className="lx-note">© 2026 VisionX team · Apache License 2.0</span>
          <button type="button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
            Back to top <span aria-hidden="true">↑</span>
          </button>
        </div>
      </div>
    </footer>
  );
}
