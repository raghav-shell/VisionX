"use client";

import React, { useState, useEffect, useRef } from "react";
import { ArrowRight, Terminal } from "lucide-react";

export default function Hero() {
  const words = ["verifies", "protects", "audits", "seals"];
  const [wordIndex, setWordIndex] = useState(0);
  const [fadeState, setFadeState] = useState<"in" | "out">("in");
  const videoRef = useRef<HTMLVideoElement>(null);

  const colors = [
    "rgb(236, 168, 214)", // pink
    "rgb(197, 151, 235)", // purple
    "rgb(158, 152, 250)", // indigo
    "rgb(121, 205, 249)", // cyan
    "rgb(145, 220, 188)", // mint
    "rgb(230, 197, 66)",  // gold
    "rgb(245, 181, 112)", // orange
    "rgb(236, 168, 214)", // pink
  ];

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    video.defaultMuted = true;
    video.muted = true;
    video.playsInline = true;

    const playVideo = () => {
      const promise = video.play();
      if (promise !== undefined) {
        promise.catch(() => {});
      }
    };

    video.addEventListener("loadeddata", playVideo);
    video.addEventListener("canplay", playVideo);
    video.addEventListener("loadedmetadata", playVideo);
    playVideo();

    return () => {
      video.removeEventListener("loadeddata", playVideo);
      video.removeEventListener("canplay", playVideo);
      video.removeEventListener("loadedmetadata", playVideo);
    };
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setFadeState("out");
      setTimeout(() => {
        setWordIndex((prev) => (prev + 1) % words.length);
        setFadeState("in");
      }, 400);
    }, 3600);
    return () => clearInterval(interval);
  }, [words.length]);

  const currentWord = words[wordIndex];

  return (
    <section className="relative h-screen min-h-[640px] max-h-[1080px] flex flex-col justify-between overflow-hidden bg-black select-none">
      {/* Background Video with local instant load, 4K contrast sharpening & Safari autoplay */}
      <div className="absolute inset-0 z-0">
        <video
          ref={videoRef}
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          controls={false}
          disablePictureInPicture
          disableRemotePlayback
          tabIndex={-1}
          aria-hidden="true"
          className="w-full h-full object-cover object-[78%_center] lg:object-[75%_center] contrast-[1.08] saturate-[1.12] brightness-[1.02] pointer-events-none"
          style={{
            imageRendering: "-webkit-optimize-contrast",
            transform: "translate3d(0, 0, 0)",
            backfaceVisibility: "hidden",
          }}
        >
          <source src="/bg-hero.mp4" type="video/mp4" />
          <source
            src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/bg-hero-0BnFGdr81Ifnj3WbBZoNt1KE4D5DMT.mp4"
            type="video/mp4"
          />
        </video>
        {/* Dark Scrim Gradients matching source website — right side stays luminous & clear */}
        <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/35 to-transparent pointer-events-none"></div>
        <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-transparent to-black/75 pointer-events-none"></div>
      </div>

      {/* Grid Lines Overlay */}
      <div className="absolute inset-0 z-[2] overflow-hidden pointer-events-none opacity-20">
        <div className="absolute h-px bg-white/10" style={{ top: "12.5%", left: 0, right: 0 }}></div>
        <div className="absolute h-px bg-white/10" style={{ top: "25%", left: 0, right: 0 }}></div>
        <div className="absolute h-px bg-white/10" style={{ top: "37.5%", left: 0, right: 0 }}></div>
        <div className="absolute h-px bg-white/10" style={{ top: "50%", left: 0, right: 0 }}></div>
        <div className="absolute h-px bg-white/10" style={{ top: "62.5%", left: 0, right: 0 }}></div>
        <div className="absolute h-px bg-white/10" style={{ top: "75%", left: 0, right: 0 }}></div>
        <div className="absolute h-px bg-white/10" style={{ top: "87.5%", left: 0, right: 0 }}></div>

        <div className="absolute w-px bg-white/10" style={{ left: "8.33%", top: 0, bottom: 0 }}></div>
        <div className="absolute w-px bg-white/10" style={{ left: "16.66%", top: 0, bottom: 0 }}></div>
        <div className="absolute w-px bg-white/10" style={{ left: "25%", top: 0, bottom: 0 }}></div>
        <div className="absolute w-px bg-white/10" style={{ left: "33.32%", top: 0, bottom: 0 }}></div>
        <div className="absolute w-px bg-white/10" style={{ left: "41.65%", top: 0, bottom: 0 }}></div>
        <div className="absolute w-px bg-white/10" style={{ left: "50%", top: 0, bottom: 0 }}></div>
        <div className="absolute w-px bg-white/10" style={{ left: "58.31%", top: 0, bottom: 0 }}></div>
        <div className="absolute w-px bg-white/10" style={{ left: "66.64%", top: 0, bottom: 0 }}></div>
        <div className="absolute w-px bg-white/10" style={{ left: "74.97%", top: 0, bottom: 0 }}></div>
        <div className="absolute w-px bg-white/10" style={{ left: "83.3%", top: 0, bottom: 0 }}></div>
        <div className="absolute w-px bg-white/10" style={{ left: "91.63%", top: 0, bottom: 0 }}></div>
      </div>

      {/* Hero Content */}
      <div className="relative z-10 w-full max-w-[1400px] mx-auto px-6 lg:px-12 pt-28 lg:pt-32 pb-4 flex-1 flex flex-col justify-center">
        <div className="max-w-2xl lg:max-w-[54%]">
          {/* Eyebrow */}
          <div className="mb-6 lg:mb-8 animate-fade-slide-in">
            <span className="inline-flex items-center gap-3 text-xs md:text-sm font-mono text-white/60 tracking-wide">
              <span className="w-8 h-px bg-[#eca8d6]"></span>
              Air-Gapped Computer-Vision Assurance · VisionX Core
            </span>
          </div>

          {/* Headline with Rainbow Pastel Glow Word */}
          <div className="mb-6 lg:mb-8">
            <h1 className="text-left text-[clamp(2.4rem,5.6vw,5.6rem)] font-display font-semibold leading-[0.92] tracking-tight text-white">
              <span className="block whitespace-nowrap">Computer-vision integrity,</span>
              <span className="block whitespace-nowrap">
                assurance that{" "}
                <span className="relative inline-block">
                  {currentWord.split("").map((letter, i) => (
                    <span
                      key={i}
                      style={{
                        display: "inline-block",
                        opacity: fadeState === "in" ? 1 : 0,
                        filter: fadeState === "in" ? "blur(0px)" : "blur(14px)",
                        color: colors[i % colors.length],
                        transition: `all 400ms cubic-bezier(0.16, 1, 0.3, 1) ${i * 45}ms`,
                        textShadow:
                          fadeState === "in"
                            ? `0 0 24px ${colors[i % colors.length]}, 0 0 48px ${colors[i % colors.length]}`
                            : "none",
                      }}
                      className="font-bold"
                    >
                      {letter}
                    </span>
                  ))}
                </span>
              </span>
            </h1>
          </div>

          {/* Description */}
          <p className="text-base md:text-lg text-white/65 leading-relaxed max-w-xl mb-8 font-normal">
            Independent, offline audit across training data, model checkpoints, and inference
            provenance. Sealed with RFC 8785 Ed25519 Merkle ledgers.
          </p>

          {/* Action CTAs */}
          <div className="flex flex-wrap items-center gap-3">
            <a
              href="/workspace"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-white text-black px-6 py-3 text-sm font-semibold hover:bg-white/90 hover:scale-[1.02] active:scale-[0.98] transition-all shadow-lg shadow-white/10"
            >
              <span>Get Started</span>
              <ArrowRight className="w-4 h-4" />
            </a>
            <a
              href="#console"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-white/10 hover:bg-white/15 border border-white/20 text-white px-5 py-3 text-sm font-medium transition-all backdrop-blur-md"
            >
              <Terminal className="w-4 h-4 text-[#eca8d6]" />
              <span>Interactive CLI</span>
            </a>
          </div>
        </div>
      </div>

      {/* Bottom Live Metrics Bar matching source layout */}
      <div className="relative z-10 w-full max-w-[1400px] mx-auto px-6 lg:px-12 pb-10 lg:pb-14">
        <div className="flex items-start gap-10 lg:gap-20">
          <div className="flex flex-col gap-1.5">
            <span className="text-3xl lg:text-4xl font-display text-white tracking-tight">100%</span>
            <span className="text-xs text-white/50 leading-tight font-sans">air-gapped &amp; offline</span>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-3xl lg:text-4xl font-display text-white tracking-tight">RFC 8785</span>
            <span className="text-xs text-white/50 leading-tight font-sans">Ed25519 Merkle ledgers</span>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-3xl lg:text-4xl font-display text-white tracking-tight">&lt;12ms</span>
            <span className="text-xs text-white/50 leading-tight font-sans">adversarial scan latency</span>
          </div>
        </div>
      </div>
    </section>
  );
}
