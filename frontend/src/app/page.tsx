import { Hero } from "@/components/landing/hero";
import {
  Accuracy,
  CallToAction,
  Capabilities,
  HowItWorks,
  PassportTrust,
  PassportSection,
} from "@/components/landing/sections";

export default function LandingPage() {
  return (
    <>
      <Hero />
      <Capabilities />
      <HowItWorks />
      <Accuracy />
      <PassportSection />
      <PassportTrust />
      <CallToAction />
    </>
  );
}
