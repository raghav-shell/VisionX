"use client";

import React, { useEffect, useRef, useState } from "react";

interface ScrollRevealProps {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  direction?: "up" | "scale" | "fade";
}

export default function ScrollReveal({
  children,
  className = "",
  delay = 0,
  direction = "up",
}: ScrollRevealProps) {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !("IntersectionObserver" in window)) {
      setIsVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          if (ref.current) {
            observer.unobserve(ref.current);
          }
        }
      },
      {
        threshold: 0.08,
        rootMargin: "0px 0px -60px 0px", // triggers cleanly as user scrolls down
      }
    );

    const currentRef = ref.current;
    if (currentRef) {
      observer.observe(currentRef);
    }

    return () => {
      if (currentRef) {
        observer.unobserve(currentRef);
      }
      observer.disconnect();
    };
  }, []);

  const getHiddenTransform = () => {
    switch (direction) {
      case "scale":
        return "opacity-0 scale-95 blur-[2px]";
      case "fade":
        return "opacity-0";
      case "up":
      default:
        // Punchy upward slide + subtle scale expansion for the satisfying "pop-in" effect
        return "opacity-0 translate-y-16 scale-[0.97]";
    }
  };

  const getVisibleTransform = () => {
    return "opacity-100 translate-y-0 scale-100";
  };

  return (
    <div
      ref={ref}
      style={{
        transitionDuration: "850ms",
        transitionDelay: `${delay}ms`,
        transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)", // signature Apple/Vercel spring-out
      }}
      className={`transition-all will-change-transform ${
        isVisible ? getVisibleTransform() : getHiddenTransform()
      } ${className}`}
    >
      {children}
    </div>
  );
}
