"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";

const WORDS = ["audit", "verify", "trace", "inspect"];

const FACTS = [
  { value: "23", text: "detectors across data, models, provenance, drift and governance." },
  { value: "5", text: "coverage states, so a check that never ran can't pass for one that did." },
  { value: "2", text: "people to change a disposition. The backend refuses self-approval." },
];

export default function Hero() {
  const [wordIndex, setWordIndex] = useState(0);
  const [isExiting, setIsExiting] = useState(false);
  // Keep the server and first client render identical: browser extensions can
  // inject controls into a <video> before React hydrates it.
  const [showVideo, setShowVideo] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    setShowVideo(true);
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.defaultMuted = true;
    video.muted = true;
    video.playsInline = true;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      video.removeAttribute("autoplay");
      video.pause();
      return;
    }
    const play = () => {
      video.play()?.catch(() => {});
    };
    video.addEventListener("loadeddata", play);
    video.addEventListener("canplay", play);
    play();
    return () => {
      video.removeEventListener("loadeddata", play);
      video.removeEventListener("canplay", play);
    };
  }, [showVideo]);

  // The word changes every four seconds, letter by letter.
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const exit = window.setTimeout(() => setIsExiting(true), 3200);
    const next = window.setTimeout(() => {
      setWordIndex((index) => (index + 1) % WORDS.length);
      setIsExiting(false);
    }, 3700);
    return () => {
      window.clearTimeout(exit);
      window.clearTimeout(next);
    };
  }, [wordIndex]);

  const word = WORDS[wordIndex];

  return (
    <section id="top" className="lx-hero" aria-labelledby="lx-hero-title">
      <div className="lx-hero-media" aria-hidden="true">
        {showVideo && (
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
          >
            <source src="/bg-hero.mp4" type="video/mp4" />
          </video>
        )}
      </div>
      <div className="lx-hero-rules" aria-hidden="true" />

      <div className="lx-shell lx-hero-body">
        <p className="lx-eyebrow">
          <span>
            <span className="n">SIH26228</span> · Offline assurance for computer vision
          </span>
        </p>

        <h1 id="lx-hero-title" className="lx-display">
          <span className="block">Computer vision</span>
          <span className="block">
            you can{" "}
            <span className="lx-word" aria-live="off">
              <span className="sr-only">{word}</span>
              <span aria-hidden="true">
                {word.split("").map((letter, i) => (
                  <span
                    key={`${wordIndex}-${i}`}
                    className={`lx-letter ${isExiting ? "lx-letter--out" : ""}`}
                    style={{ animationDelay: isExiting ? `${(word.length - 1 - i) * 40}ms` : `${i * 90}ms` }}
                  >
                    {letter}
                  </span>
                ))}
              </span>
            </span>
          </span>
        </h1>

        <p className="lx-lede">
          VisionX checks the datasets, models and inference records your contributors hand over, on your own
          machine. Every finding opens to the images and numbers behind it.
        </p>

        <div className="lx-actions">
          <Link href="/workspace" className="lx-btn lx-btn--primary">
            Open the workspace <span className="ar" aria-hidden="true">→</span>
          </Link>
          <a href="#demo" className="lx-btn lx-btn--ghost">
            See it catch an attack <span className="ar ar--down" aria-hidden="true">↓</span>
          </a>
        </div>
      </div>

      <div className="lx-shell">
        <ul className="lx-facts">
          {FACTS.map((fact) => (
            <li key={fact.value}>
              <b>{fact.value}</b>
              <span>{fact.text}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
