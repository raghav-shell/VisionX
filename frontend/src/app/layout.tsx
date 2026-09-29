import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VisionX — Offline Computer Vision Assurance",
  description:
    "Assess vision datasets and models locally. Inspect findings, coverage, and evidence; verify signed inference records offline.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark scroll-smooth">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Space+Grotesk:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        <link rel="icon" href="/visionx-logo.png" />
      </head>
      <body className="bg-black text-white min-h-screen selection:bg-[#eca8d6] selection:text-black">
        {children}
      </body>
    </html>
  );
}
