import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Capabilities from "@/components/Capabilities";
import Process from "@/components/Process";
import Infrastructure from "@/components/Infrastructure";
import SignalMetrics from "@/components/SignalMetrics";
import Security from "@/components/Security";
import Integrations from "@/components/Integrations";
import DeveloperSDK from "@/components/DeveloperSDK";
import InteractiveConsole from "@/components/InteractiveConsole";
import Validation from "@/components/Validation";
import CTASection from "@/components/CTASection";
import Footer from "@/components/Footer";
import ScrollReveal from "@/components/ScrollReveal";

export default function Home() {
  return (
    <main className="relative min-h-screen bg-black text-white selection:bg-[#eca8d6] selection:text-black overflow-x-clip">
      <Navbar />
      <Hero />

      {/* Each section pops in smoothly as user scrolls down */}
      <ScrollReveal direction="up">
        <Capabilities />
      </ScrollReveal>

      <ScrollReveal direction="up">
        <Process />
      </ScrollReveal>

      <ScrollReveal direction="up">
        <Infrastructure />
      </ScrollReveal>

      <ScrollReveal direction="up">
        <SignalMetrics />
      </ScrollReveal>

      <ScrollReveal direction="up">
        <Integrations />
      </ScrollReveal>

      <ScrollReveal direction="up">
        <Security />
      </ScrollReveal>

      <ScrollReveal direction="up">
        <DeveloperSDK />
      </ScrollReveal>

      <InteractiveConsole />

      <ScrollReveal direction="up">
        <Validation />
      </ScrollReveal>

      <CTASection />

      <div aria-hidden="true" className="h-[clamp(220px,38svh,500px)] bg-black" />

      <Footer />
    </main>
  );
}
