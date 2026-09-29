"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Menu, X, ArrowUpRight, ShieldCheck } from "lucide-react";
import VisionXLogo from "./VisionXLogo";

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const navLinks = [
    { name: "Capabilities", href: "#capabilities" },
    { name: "Process", href: "#process" },
    { name: "Offline Design", href: "#infra" },
    { name: "Signals", href: "#signals" },
    { name: "Integrations", href: "#integrations" },
    { name: "Security", href: "#security" },
    { name: "Console", href: "#console" },
  ];

  return (
    <header
      className={`fixed z-50 transition-all duration-500 left-0 right-0 ${
        scrolled ? "top-3 px-4" : "top-0 px-0"
      }`}
    >
      <nav
        className={`mx-auto transition-all duration-500 ${
          scrolled || mobileMenuOpen
            ? "bg-black/80 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl max-w-[1200px]"
            : "bg-transparent max-w-[1400px] border-b border-white/[0.04]"
        }`}
      >
        <div
          className={`flex items-center justify-between transition-all duration-500 px-6 lg:px-8 ${
            scrolled ? "h-14" : "h-20"
          }`}
        >
          {/* Brand Logo */}
          <Link href="/" className="flex items-center gap-3 group">
            <VisionXLogo size={scrolled ? 26 : 30} />
            <div className="flex flex-col">
              <span
                className={`font-display tracking-tight transition-all duration-500 font-bold text-white flex items-center gap-1.5 ${
                  scrolled ? "text-lg" : "text-xl"
                }`}
              >
                Vision<span className="bg-gradient-to-r from-[#eca8d6] via-[#c597eb] to-[#a78bfa] bg-clip-text text-transparent font-extrabold">X</span>
                <span className="w-1.5 h-1.5 rounded-full bg-[#eca8d6] animate-pulse" />
              </span>
              <span
                className={`font-mono transition-all duration-500 tracking-wider uppercase ${
                  scrolled ? "text-[8px] text-white/40" : "text-[9px] text-white/50"
                }`}
              >
                Integrity Engine
              </span>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          <div
            className={`hidden xl:flex items-center transition-all duration-500 ${
              scrolled ? "gap-8" : "gap-10"
            }`}
          >
            {navLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                className="text-xs font-mono text-white/70 hover:text-white transition-colors duration-200"
              >
                {link.name}
              </a>
            ))}
          </div>

          {/* Right Action Buttons */}
          <div className="hidden xl:flex items-center gap-4">
            <Link
              href="/workspace"
              className="text-xs font-mono text-white/70 hover:text-white transition-colors px-3 py-1.5"
            >
              Demo
            </Link>

            <Link
              href="/workspace"
              className="inline-flex items-center gap-1.5 rounded-full bg-white text-black px-4 py-2 text-xs font-semibold hover:bg-white/90 hover:scale-[1.02] active:scale-[0.98] transition-all shadow-lg shadow-white/10"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Explore demo</span>
            </Link>
          </div>

          {/* Mobile Hamburger Toggle */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="xl:hidden p-2 text-white/80 hover:text-white"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="xl:hidden border-t border-white/10 px-6 py-6 space-y-4 bg-black/95 rounded-b-2xl">
            {navLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="block text-sm font-mono text-white/80 hover:text-white py-1"
              >
                {link.name}
              </a>
            ))}
            <div className="pt-4 border-t border-white/10 flex flex-col gap-3">
              <Link
                href="/workspace"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center py-2.5 rounded-full bg-white text-black text-xs font-semibold"
              >
                Explore demo
              </Link>
            </div>
          </div>
        )}
      </nav>
    </header>
  );
}
