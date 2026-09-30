import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        hv: {
          bg: "var(--hv-bg)",
          surface: "var(--hv-surface)",
          sunken: "var(--hv-sunken)",
          raised: "var(--hv-raised)",
          ink: "var(--hv-ink)",
          ink2: "var(--hv-ink-2)",
          muted: "var(--hv-muted)",
          line: "var(--hv-line)",
          lineStrong: "var(--hv-line-strong)",
          lime: "var(--hv-lime)",
          limeHover: "var(--hv-lime-hover)",
          limeInk: "var(--hv-lime-ink)",
          ok: "var(--hv-ok)",
          info: "var(--hv-info)",
          held: "var(--hv-held)",
          bad: "var(--hv-bad)",
        },
        background: "#000000",
        foreground: "#ffffff",
        card: {
          DEFAULT: "rgba(10, 10, 12, 0.6)",
          hover: "rgba(20, 20, 24, 0.8)",
          solid: "#0c0c0e",
        },
        accent: {
          pink: "#eca8d6",
          purple: "#c597eb",
          indigo: "#9e98fa",
          cyan: "#79cdf9",
          mint: "#91dcbc",
          amber: "#e6c542",
          orange: "#f5b570",
        },
        muted: {
          DEFAULT: "rgba(255, 255, 255, 0.5)",
          foreground: "rgba(255, 255, 255, 0.6)",
          dark: "rgba(255, 255, 255, 0.2)",
        },
        border: "rgba(255, 255, 255, 0.1)",
      },
      fontFamily: {
        sans: ["var(--font-archivo)", "Archivo", "system-ui", "sans-serif"],
        display: ["var(--font-archivo)", "Archivo", "system-ui", "sans-serif"],
        mono: ["var(--font-martian)", "Martian Mono", "ui-monospace", "monospace"],
      },
      keyframes: {
        drawLine: {
          "0%": { strokeDashoffset: "1000", opacity: "0" },
          "15%": { opacity: "1" },
          "70%": { opacity: "0.8" },
          "100%": { strokeDashoffset: "0", opacity: "0" },
        },
        pulseGlow: {
          "0%, 100%": { transform: "scale(1)", opacity: "0.8" },
          "50%": { transform: "scale(1.4)", opacity: "0.2" },
        },
        progressBar: {
          "0%": { width: "0%" },
          "100%": { width: "100%" },
        },
        fadeSlideIn: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "draw-line": "drawLine 3s ease-in-out infinite",
        "pulse-glow": "pulseGlow 2s ease-in-out infinite",
        "progress-bar": "progressBar 6s linear forwards",
        "fade-slide-in": "fadeSlideIn 0.5s ease-out forwards",
      },
    },
  },
  plugins: [],
};

export default config;
