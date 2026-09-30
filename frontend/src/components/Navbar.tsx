"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import VisionXLogo from "./VisionXLogo";

const REPO_URL = "https://github.com/raghav-shell/VisionX";

const navLinks = [
  { n: "01", name: "How it works", href: "#demo" },
  { n: "02", name: "Checks", href: "#checks" },
  { n: "03", name: "Proof", href: "#proof" },
  { n: "04", name: "Offline", href: "#offline" },
];

export default function Navbar() {
  const header = useRef<HTMLElement>(null);
  const [open, setOpen] = useState(false);

  // Transparent over the hero, solid with a hairline once the page moves.
  useEffect(() => {
    const el = header.current;
    if (!el) return;
    const update = () => {
      if (window.scrollY > 24) el.dataset.solid = "";
      else delete el.dataset.solid;
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header ref={header} className="lx-header" style={open ? { background: "var(--hv-bg)" } : undefined}>
      <div className="lx-shell row">
        <Link href="/" aria-label="VisionX home" className="lx-home" onClick={() => setOpen(false)}>
          <VisionXLogo size={26} showText textClassName="text-[19px]" />
        </Link>

        <nav aria-label="Sections" className="lx-nav">
          {navLinks.map((link) => (
            <a key={link.href} href={link.href}>
              <span className="n">{link.n}</span>
              {link.name}
            </a>
          ))}
        </nav>

        <div className="end">
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="lx-navlink lx-hide-sm">
            GitHub
          </a>
          <Link href="/workspace" className="lx-btn lx-btn--ghost lx-btn--sm lx-hide-sm">
            Open the workspace
          </Link>
          <button
            type="button"
            className="lx-menu"
            onClick={() => setOpen((value) => !value)}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-controls="lx-mobile-nav"
            aria-expanded={open}
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {open && (
        <div id="lx-mobile-nav" className="lx-mnav">
          <div className="lx-shell">
            {navLinks.map((link) => (
              <a key={link.href} href={link.href} onClick={() => setOpen(false)}>
                {link.name}
                <span className="n">{link.n}</span>
              </a>
            ))}
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer" onClick={() => setOpen(false)}>
              GitHub
              <span className="n">SOURCE</span>
            </a>
            <div className="lx-actions">
              <Link href="/workspace" className="lx-btn lx-btn--primary" onClick={() => setOpen(false)}>
                Open the workspace <span className="ar" aria-hidden="true">→</span>
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
