import React from "react";

interface VisionXLogoProps {
  className?: string;
  size?: number;
  showText?: boolean;
  textClassName?: string;
}

// The mark and a monochrome wordmark. The workspace restyles the wordmark
// through its `text-white` class, so that class stays.
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
        className={`shrink-0 ${className}`}
      />
      {showText && (
        <span className={`font-display font-semibold leading-none tracking-[-0.04em] text-white ${textClassName}`}>
          VisionX
        </span>
      )}
    </span>
  );
}
