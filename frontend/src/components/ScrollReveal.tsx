"use client";

import React, { useEffect, useLayoutEffect, useRef } from "react";

// useLayoutEffect warns during server rendering; the server needs neither.
const useIsomorphicLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

interface ScrollRevealProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * A block that settles in once, when it is first reached: a short fade-up,
 * opacity and transform only. Nothing is hidden on the server or without
 * JavaScript, and a block already on screen at hydration is left alone, so
 * the page always reads complete. Reduced motion shows everything at once.
 */
export default function ScrollReveal({ children, className = "" }: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null);

  useIsomorphicLayoutEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const box = el.getBoundingClientRect();
    if (box.top < window.innerHeight && box.bottom > 0) return;
    el.dataset.reveal = "wait";
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          el.dataset.reveal = "in";
          io.disconnect();
        }
      },
      { threshold: 0.06, rootMargin: "0px 0px -8% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div ref={ref} className={`lx-reveal ${className}`}>
      {children}
    </div>
  );
}
