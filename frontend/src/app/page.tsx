import { Hero } from "@/components/landing/hero";
import {
  Accuracy,
  CallToAction,
  Capabilities,
  HowItWorks,
  Limits,
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
      <Limits />
      <CallToAction />
    </>
  );
}
