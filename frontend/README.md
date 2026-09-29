# VisionX Frontend

Modern dark-aesthetic cockpit and landing page for **VisionX** (VisionSentinel) — Air-Gapped Computer Vision Integrity & Assurance Platform.

---

## 🎨 Visual & Technical Architecture

- **Stack**: Next.js 15 (App Router), React 19, Tailwind CSS, Lucide Icons, Google Fonts (`Inter`, `Space Grotesk`, `JetBrains Mono`).
- **Design Tokens**:
  - Background: Pure black (`#000000`) with layered ambient dark glow gradients (`#030305`, `#08080f`).
  - Accents: Pastel neon pink (`#eca8d6`), neon purple (`#c597eb`), cyan/ice (`#9bb2ff`).
  - High-fidelity visual assets: Video background, glowing bonsai tree, network sphere, 3D real-time metric graph, glowing SVG connecting lines, animated sparklines, interactive particle canvas.
- **Animations**:
  - Letter-by-letter pastel glowing word switcher in the Hero.
  - Auto-advancing process tab progress bars.
  - SVG path stroke dashoffset drawing lines (`drawLine`).
  - Interactive HTML5 canvas particle cluster visualizer (Module A) & real-time drift chart (Module D).
  - Interactive multi-command macOS terminal simulation.

---

## 🚀 Getting Started

### 1. Run the Development Server
```bash
cd frontend
npm run dev -- -p 3001
```
Open [http://localhost:3001](http://localhost:3001) in your browser.

### 2. Build for Production
```bash
cd frontend
npm run build
npm run start -- -p 3001
```

---

## 📁 Component Directory

- `src/components/Navbar.tsx`: Floating blurred glass navigation with live status beacon.
- `src/components/Hero.tsx`: Background video hero, dynamic animated keyword cycle (`verifies`, `protects`, `audits`, `seals`), live metric badges.
- `src/components/Capabilities.tsx`: Bento grid detailing Modules A, B, C, D with interactive particle canvas and Trojan outlier graph.
- `src/components/Process.tsx`: "Ingest. Audit. Seal." with ethereal bonsai tree graphic and auto-advancing progress tabs.
- `src/components/Infrastructure.tsx`: "Offline by default" section with network sphere, animated circuit SVGs, and status nodes.
- `src/components/SignalMetrics.tsx`: Mathematical rigor showcase with 3D real-time graph graphic and live HTML5 canvas drift chart.
- `src/components/Security.tsx`: Defense-grade specification (S3 Sandbox, `SO_PEERCRED`, Four-Eyes dual signing, RFC 6962 Merkle tree).
- `src/components/Integrations.tsx`: Supported formats (PyTorch, ONNX, TorchScript, COCO, YOLO, VOC, Libsodium, Rust).
- `src/components/DeveloperSDK.tsx`: Multi-language code samples (CLI, C99 header, Rust FFI, standalone verifier).
- `src/components/InteractiveConsole.tsx`: Interactive macOS terminal preview simulating VisionX scans and cryptographic approvals.
- `src/components/Footer.tsx`: VisionX platform metadata and architecture links.
- `src/components/workspace/`: Verification cockpit studio tabs (Overview, Dataset, Trojan, Drift, SEAL wire, Ledger).
