import Link from "next/link";

const REPO_URL = "https://github.com/raghav-shell/VisionX";

export default function CTASection() {
  return (
    <section id="start" className="lx-cta" aria-labelledby="lx-cta-title">
      <img src="/images/bridge-mono.webp" alt="" aria-hidden="true" width={1400} height={933} loading="lazy" decoding="async" />
      <div className="lx-shell">
        <p className="lx-eyebrow">
          <span>
            <span className="n">SIH26228</span> · Smart India Hackathon 2026
          </span>
        </p>
        <h2 id="lx-cta-title" className="lx-h2">
          <span>Run the attack</span> <b>yourself.</b>
        </h2>
        <p className="lx-lede">
          Open the workspace, start the targeted label flip in Attack Lab and follow Charlie from the first flag to a
          signed decision. Nine more scenarios ship with it.
        </p>
        <div className="lx-actions">
          <Link href="/workspace" className="lx-btn lx-btn--primary">
            Open the workspace <span className="ar" aria-hidden="true">→</span>
          </Link>
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="lx-btn lx-btn--ghost">
            Source on GitHub <span className="ar" aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    </section>
  );
}
