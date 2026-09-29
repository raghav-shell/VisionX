"use client";

import React from "react";

interface VisionXLogoProps {
  className?: string;
  size?: number;
  showText?: boolean;
  textClassName?: string;
}

export default function VisionXLogo({
  className = "w-7 h-7",
  size = 28,
  showText = false,
  textClassName = "text-xl",
}: VisionXLogoProps) {
  return (
    <div className="inline-flex items-center gap-2.5 select-none group">
      {/* Precision Geometric Vector Emblem */}
      <div className={`relative shrink-0 flex items-center justify-center ${className}`}>
        {/* Ambient Halo Glow on Hover */}
        <div className="absolute inset-0 rounded-full bg-[#eca8d6]/25 blur-md opacity-60 group-hover:opacity-100 transition-opacity duration-500 scale-125 pointer-events-none" />

        <svg
          width={size}
          height={size}
          viewBox="0 0 48 48"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="relative z-10 transition-transform duration-500 group-hover:scale-105"
        >
          <defs>
            {/* Primary Luminous Linear Gradient */}
            <linearGradient id="vx-primary-logo" x1="4" y1="4" x2="44" y2="44" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#FFFFFF" />
              <stop offset="45%" stopColor="#ECA8D6" />
              <stop offset="100%" stopColor="#A78BFA" />
            </linearGradient>

            {/* Secondary Metallic Shading */}
            <linearGradient id="vx-metallic-logo" x1="44" y1="4" x2="4" y2="44" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#E2E8F0" />
              <stop offset="60%" stopColor="#94A3B8" />
              <stop offset="100%" stopColor="#475569" />
            </linearGradient>
          </defs>

          {/* Outer Concentric Optical Iris Rings */}
          <circle cx="24" cy="24" r="21" stroke="white" strokeOpacity="0.15" strokeWidth="1" />
          <circle cx="24" cy="24" r="17" stroke="url(#vx-primary-logo)" strokeOpacity="0.4" strokeWidth="1.2" strokeDasharray="3 2" />
          <circle cx="24" cy="24" r="12" stroke="white" strokeOpacity="0.2" strokeWidth="1" />

          {/* Top-Left to Bottom-Right Aerodynamic Wing */}
          <path
            d="M 9 9 C 17 15, 20 20, 24 24 C 28 28, 31 33, 39 39 C 32 35, 27 30, 24 24 C 21 18, 16 13, 9 9 Z"
            fill="url(#vx-primary-logo)"
          />

          {/* Top-Right to Bottom-Left Aerodynamic Wing */}
          <path
            d="M 39 9 C 31 15, 28 20, 24 24 C 20 28, 17 33, 9 39 C 16 35, 21 30, 24 24 C 27 18, 32 13, 39 9 Z"
            fill="url(#vx-metallic-logo)"
          />

          {/* Inner Sharp Precision X Chevrons */}
          <path
            d="M 14 11 L 24 22 L 34 11 L 24 20 Z"
            fill="#FFFFFF"
            fillOpacity="0.9"
          />
          <path
            d="M 14 37 L 24 26 L 34 37 L 24 28 Z"
            fill="url(#vx-primary-logo)"
          />

          {/* Core Optical Aperture Pupil */}
          <circle cx="24" cy="24" r="5" fill="#000000" stroke="url(#vx-primary-logo)" strokeWidth="1.5" />
          <circle cx="24" cy="24" r="2" fill="#FFFFFF" />
        </svg>
      </div>

      {/* Typography with Gradient Accent */}
      {showText && (
        <div className="flex items-center gap-1.5">
          <span className={`font-display tracking-tight font-semibold text-white ${textClassName}`}>
            Vision
            <span className="bg-gradient-to-r from-[#eca8d6] via-[#c597eb] to-[#a78bfa] bg-clip-text text-transparent font-bold">
              X
            </span>
          </span>
          <span className="font-mono text-[9px] uppercase tracking-wider text-[#eca8d6] bg-[#eca8d6]/10 border border-[#eca8d6]/25 px-1.5 py-0.5 rounded-full">
            TM
          </span>
        </div>
      )}
    </div>
  );
}
