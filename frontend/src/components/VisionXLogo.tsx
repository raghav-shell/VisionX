import React from "react";

interface VisionXLogoProps {
  className?: string;
  size?: number;
  showText?: boolean;
  textClassName?: string;
}

export default function VisionXLogo({
  className = "",
  size = 32,
  showText = false,
  textClassName = "text-[22px]",
}: VisionXLogoProps) {
  return (
    <span className="inline-flex items-center gap-2.5 select-none whitespace-nowrap">
      <img
        src="/visionx-mark.svg"
        alt=""
        aria-hidden="true"
        width={size}
        height={size}
        className={`shrink-0 transition-transform duration-300 group-hover:scale-[1.04] ${className}`}
      />
      {showText && (
        <span className={`font-display font-semibold leading-none tracking-[-0.055em] text-white ${textClassName}`}>
          Vision<span className="text-[#E5B5D7]">X</span>
        </span>
      )}
    </span>
  );
}
