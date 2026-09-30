import type { Metadata } from "next";
import localFont from "next/font/local";
import "./hivis.css";
import "./globals.css";

// Hi-Vis Monochrome type, bundled (SIL OFL) so the air-gapped build fetches nothing.
const archivo = localFont({
  src: "./fonts/archivo-variable.woff2",
  weight: "100 900",
  // The width axis must be declared on the @font-face or font-stretch selects nothing.
  declarations: [{ prop: "font-stretch", value: "62% 125%" }],
  variable: "--font-archivo",
  display: "swap",
});

const martian = localFont({
  src: "./fonts/martian-mono-variable.woff2",
  weight: "100 800",
  variable: "--font-martian",
  display: "swap",
});

export const metadata: Metadata = {
  title: "VisionX · Offline assurance for computer vision",
  description:
    "Check vision datasets, models and inference records on your own machine. Every finding comes with its evidence, what was not checked, and who signed off.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark scroll-smooth ${archivo.variable} ${martian.variable}`}>
      <head>
        <link rel="icon" href="/visionx-mark.svg" type="image/svg+xml" />
      </head>
      <body className="bg-[var(--hv-bg)] text-[var(--hv-ink)] min-h-screen font-sans selection:bg-[#d4f24a] selection:text-black">
        {children}
      </body>
    </html>
  );
}
