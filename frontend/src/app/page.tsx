import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Process from "@/components/Process";
import Capabilities from "@/components/Capabilities";
import Validation from "@/components/Validation";
import Security from "@/components/Security";
import CTASection from "@/components/CTASection";
import Footer from "@/components/Footer";
import ScrollReveal from "@/components/ScrollReveal";

// The public page: what VisionX is, one recorded attack caught end to end,
// what it checks, the measured results with their misses, how it stays
// offline, and a way in.
export default function Home() {
  return (
    <main className="lx">
      <Navbar />
      <Hero />
      <ScrollReveal>
        <Process />
      </ScrollReveal>
      <ScrollReveal>
        <Capabilities />
      </ScrollReveal>
      <ScrollReveal>
        <Validation />
      </ScrollReveal>
      <ScrollReveal>
        <Security />
      </ScrollReveal>
      <CTASection />
      <Footer />
    </main>
  );
}
