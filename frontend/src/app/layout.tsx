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
        <link rel="icon" href="/visionx-mark.svg" type="image/svg+xml" />
      </head>
      <body className="bg-black text-white min-h-screen selection:bg-[#eca8d6] selection:text-black">
        {children}
      </body>
    </html>
  );
}
