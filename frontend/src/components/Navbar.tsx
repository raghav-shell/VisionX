"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Menu, X } from "lucide-react";
import VisionXLogo from "./VisionXLogo";

const navLinks = [
  { name: "Capabilities", href: "#capabilities" },
  { name: "Process", href: "#process" },
  { name: "Offline design", href: "#infra" },
  { name: "Integrations", href: "#integrations" },
  { name: "Security", href: "#security" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileMenuOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [mobileMenuOpen]);

  return (
    <header className="pointer-events-none fixed inset-x-0 top-4 z-50 px-4 lg:top-5 lg:px-8">
      <nav
        aria-label="Main navigation"
        className={`pointer-events-auto mx-auto max-w-[1240px] overflow-hidden rounded-[22px] border border-white/[0.13] shadow-[0_18px_60px_rgba(0,0,0,0.35)] transition-colors duration-300 ${
          scrolled || mobileMenuOpen ? "bg-[#09090b]/95 backdrop-blur-2xl" : "bg-black/80 backdrop-blur-xl"
        }`}
      >
        <div className="grid h-[68px] grid-cols-[1fr_auto] items-center px-5 sm:px-7 lg:h-[72px] lg:grid-cols-[1fr_auto_1fr] lg:px-8">
          <Link
            href="/"
            aria-label="VisionX home"
            className="group inline-flex w-fit items-center focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#E5B5D7]"
            onClick={() => setMobileMenuOpen(false)}
          >
            <VisionXLogo size={33} showText textClassName="text-[23px]" />
          </Link>

          <div className="hidden items-center gap-6 lg:flex xl:gap-9">
            {navLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                className="whitespace-nowrap text-[13px] font-medium text-white/55 transition-colors hover:text-white focus-visible:text-white focus-visible:outline-none"
              >
                {link.name}
              </a>
            ))}
          </div>

          <div className="hidden items-center justify-end gap-6 lg:flex">
            <a
              href="https://github.com/raghav-shell/VisionX"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[13px] font-medium text-white/55 transition-colors hover:text-white focus-visible:text-white focus-visible:outline-none"
            >
              GitHub <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
            <Link
              href="/workspace"
              className="inline-flex h-10 items-center justify-center rounded-full bg-[#f5f3f4] px-5 text-[13px] font-semibold text-[#111014] shadow-[0_4px_20px_rgba(255,255,255,0.12)] transition-colors hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#E5B5D7]"
            >
              Open demo
            </Link>
          </div>

          <button
            type="button"
            onClick={() => setMobileMenuOpen((open) => !open)}
            className="justify-self-end rounded-lg p-2 text-white/80 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#E5B5D7] lg:hidden"
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
            aria-controls="mobile-navigation"
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {mobileMenuOpen && (
          <div id="mobile-navigation" className="border-t border-white/10 px-5 pb-5 pt-3 sm:px-7 lg:hidden">
            {navLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="block rounded-lg px-2 py-2.5 text-sm text-white/70 transition-colors hover:bg-white/5 hover:text-white"
              >
                {link.name}
              </a>
            ))}
            <div className="mt-3 flex items-center justify-between gap-4 border-t border-white/10 pt-4">
              <a
                href="https://github.com/raghav-shell/VisionX"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-sm text-white/60 hover:text-white"
              >
                GitHub <ArrowUpRight className="h-4 w-4" />
              </a>
              <Link
                href="/workspace"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-black"
              >
                Open demo
              </Link>
            </div>
          </div>
        )}
      </nav>
    </header>
  );
}
