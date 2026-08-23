import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  BadgeCheck,
  FileSignature,
  Layers,
  ShieldHalf,
  Thermometer,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  ACCURACY_NOTE,
  ACCURACY_ROWS,
  CAPABILITIES,
  CTA,
  HOW_IT_WORKS,
  PASSPORT_FLOW,
  PASSPORT_SECTION,
} from "@/lib/constants";
import { cn } from "@/lib/utils";

function Shell({
  children,
  className,
  id,
}: {
  children: React.ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={cn("px-5 py-20 sm:px-8 sm:py-28", className)}>
      <div className="mx-auto max-w-[1320px]">{children}</div>
    </section>
  );
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="eyebrow inline-flex items-center gap-2">
      <span className="h-px w-6 bg-ink-soft/40" />
      {children}
    </span>
  );
}

/* ============================================================ capabilities */

const ICONS = [Activity, Layers, ShieldHalf, Thermometer, BadgeCheck, FileSignature];

export function Capabilities() {
  return (
    <Shell id="capabilities">
      <div className="grid gap-8 lg:grid-cols-[1fr_1.1fr] lg:items-end">
        <div>
          <Eyebrow>What it reports</Eyebrow>
          <h2 className="font-display mt-5 text-[clamp(2rem,4.2vw,3.25rem)] leading-[1.02] font-bold text-balance">
            Six answers from
            <br />
            one charge cycle
          </h2>
        </div>
        <p className="text-[14.5px] leading-relaxed text-ink-soft lg:pb-3">
          Each block below is produced by a separately validated component, and each is
          labelled with how it was obtained. A number the model inferred is never
          presented the same way as a number that was measured.
        </p>
      </div>

      <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
        {CAPABILITIES.map((item, i) => {
          const Icon = ICONS[i % ICONS.length];
          return (
            <div key={item.title} className="bg-paper p-7">
              <div className="flex items-center justify-between">
                <span className="inline-flex size-9 items-center justify-center rounded-lg bg-mist text-ink">
                  <Icon className="size-4" />
                </span>
                <span className="eyebrow">{item.tag}</span>
              </div>
              <h3 className="mt-6 text-[17px] font-semibold tracking-[-0.015em]">
                {item.title}
              </h3>
              <p className="mt-2.5 text-[13.5px] leading-relaxed text-ink-soft">
                {item.body}
              </p>
            </div>
          );
        })}
      </div>
    </Shell>
  );
}

/* ============================================================ how it works */

export function HowItWorks() {
  return (
    <Shell id="how-it-works" className="bg-mist/50">
      <div className="max-w-2xl">
        <Eyebrow>How it works</Eyebrow>
        <h2 className="font-display mt-5 text-[clamp(2rem,4.2vw,3.25rem)] leading-[1.02] font-bold text-balance">
          Four steps, in this order
        </h2>
        <p className="mt-5 text-[14.5px] leading-relaxed text-ink-soft">
          The order matters, which is why these are numbered: each step determines which
          model the next one is allowed to use.
        </p>
      </div>

      <ol className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-2 xl:grid-cols-4">
        {HOW_IT_WORKS.map((step, i) => (
          <li key={step.step} className="bg-paper p-7">
            <span className="font-mono text-[12px] font-semibold text-estimated">
              {String(i + 1).padStart(2, "0")}
            </span>
            <h3 className="mt-5 text-[17px] font-semibold tracking-[-0.015em]">
              {step.step}
            </h3>
            <p className="mt-2.5 text-[13.5px] leading-relaxed text-ink-soft">
              {step.body}
            </p>
          </li>
        ))}
      </ol>
    </Shell>
  );
}

/* ================================================================ accuracy */

export function Accuracy() {
  return (
    <Shell id="accuracy">
      <div className="grid grid-cols-1 gap-10 lg:grid-cols-[0.85fr_1.15fr] lg:gap-16">
        <div>
          <Eyebrow>Measured accuracy</Eyebrow>
          <h2 className="font-display mt-5 text-[clamp(2rem,4.2vw,3.25rem)] leading-[1.02] font-bold text-balance">
            The number you get is the one measured for your inputs
          </h2>
          <p className="mt-5 text-[14.5px] leading-relaxed text-ink-soft">
            {ACCURACY_NOTE}
          </p>
          <div className="mt-7">
            <Button variant="outline" asChild>
              <Link href="/dashboard?view=own">
                See which tier your data reaches
                <ArrowUpRight />
              </Link>
            </Button>
          </div>
        </div>

        <div className="min-w-0 rounded-2xl border border-line bg-paper p-2 sm:p-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tier</TableHead>
                <TableHead>What you supply</TableHead>
                <TableHead className="text-right">MAE</TableHead>
                <TableHead className="text-right">R²</TableHead>
                <TableHead className="text-right">Output</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {ACCURACY_ROWS.map((row) => (
                <TableRow key={row.tier} className={cn(!row.reliable && "text-ink-soft")}>
                  <TableCell className="whitespace-nowrap">
                    <div className="font-medium">{row.tier}</div>
                    <div className="text-[11.5px] text-ink-soft">{row.name}</div>
                  </TableCell>
                  <TableCell className="text-[12.5px] text-ink-soft">{row.input}</TableCell>
                  <TableCell className="text-right tabular font-medium whitespace-nowrap">
                    {row.mae} pts
                  </TableCell>
                  <TableCell className="text-right tabular whitespace-nowrap">
                    {row.r2}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge variant={row.reliable ? "good" : "warn"}>
                      {row.reliable ? "Full report" : "Indicative"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </Shell>
  );
}

/* ================================================================ passport */

export function PassportSection() {
  return (
    <Shell id="passport">
      <div className="overflow-hidden rounded-[26px] bg-ink text-white">
        <div className="grid gap-10 p-8 sm:p-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16 lg:p-16">
          <div>
            <span className="eyebrow text-white/50">{PASSPORT_SECTION.eyebrow}</span>
            <h2 className="font-display mt-5 text-[clamp(1.9rem,3.8vw,3rem)] leading-[1.04] font-bold text-balance">
              {PASSPORT_SECTION.title}
            </h2>
            <p className="mt-6 text-[14.5px] leading-relaxed text-white/65">
              {PASSPORT_SECTION.body}
            </p>
            <ul className="mt-8 grid gap-3">
              {PASSPORT_SECTION.bullets.map((b) => (
                <li key={b} className="flex gap-3 text-[13.5px] leading-relaxed text-white/80">
                  <BadgeCheck className="mt-0.5 size-4 shrink-0 text-white/45" />
                  {b}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-white/12 bg-white/[0.04] p-5">
            <div className="flex items-center justify-between">
              <span className="eyebrow text-white/45">passport.json</span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-semibold text-white/80">
                <span className="size-1.5 rounded-full bg-good" />
                verified
              </span>
            </div>
            <pre className="mt-4 overflow-x-auto font-mono text-[11.5px] leading-[1.75] text-white/70">
{`{
  "payload": {
    "battery": { "battery_id": "B0005" },
    "health_estimate": {
      "soh_percent": 78.4,
      "confidence_interval_90": [0.749, 0.819],
      "method": "ESTIMATED"
    },
    "second_life_assessment": {
      "grade": "B",
      "grade_confidence": "MEDIUM"
    },
    "certified_test_status": "NOT_PERFORMED"
  },
  "signature": {
    "algorithm": "Ed25519",
    "value": "9f2c…a71b"
  }
}`}
            </pre>
            <p className="mt-4 border-t border-white/10 pt-4 text-[12px] leading-relaxed text-white/50">
              Change <span className="text-white/80">soh_percent</span> to 97.5 and the
              signature stops verifying. You can do exactly that from the dashboard.
            </p>
          </div>
        </div>
      </div>
    </Shell>
  );
}

/* ================================================================== limits */

// export function Limits() {
//   return (
//     <Shell id="limits" className="bg-mist/50">
//       <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
//         <div>
//           <Eyebrow>Where it stops working</Eyebrow>
//           <h2 className="font-display mt-5 text-[clamp(2rem,4.2vw,3.25rem)] leading-[1.02] font-bold text-balance">
//             The limits, stated up front
//           </h2>
//           <p className="mt-5 text-[14.5px] leading-relaxed text-ink-soft">
//             Knowing where a method stops working is part of reporting it honestly. None of
//             this is buried in a footnote inside the product either — the same warnings
//             appear next to the numbers they apply to.
//           </p>
//         </div>

//         <div className="rounded-2xl border border-line bg-paper px-6 sm:px-8">
//           <Accordion type="single" collapsible defaultValue="item-0">
//             {LIMITS.map((limit, i) => (
//               <AccordionItem key={limit.title} value={`item-${i}`}>
//                 <AccordionTrigger>{limit.title}</AccordionTrigger>
//                 <AccordionContent>{limit.body}</AccordionContent>
//               </AccordionItem>
//             ))}
//           </Accordion>
//         </div>
//       </div>
//     </Shell>
//   );
// }
export function PassportTrust() {
  return (
    <Shell id="passport-trust" className="bg-mist/50">
      <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
        <div>
          {/* <Eyebrow>Built for the battery lifecycle</Eyebrow>
          <h2 className="font-display mt-5 text-[clamp(2rem,4.2vw,3.25rem)] leading-[1.02] font-bold text-balance">
            From assessment to a passport you can carry forward
          </h2>
          <p className="mt-5 text-[14.5px] leading-relaxed text-ink-soft">
            BATRIS turns battery assessment into a portable record that can follow the
            battery through resale, reuse and its next stage of life.
          </p> */}
          <Eyebrow>From assessment to record</Eyebrow>

<h2 className="font-display mt-5 text-[clamp(2rem,4.2vw,3.25rem)] leading-[1.02] font-bold text-balance">
  The assessment doesn't end with a number
</h2>

<p className="mt-5 text-[14.5px] leading-relaxed text-ink-soft">
  BATRIS turns the result of a battery assessment into a portable,
  verifiable record — one that can be shared, checked and carried
  forward with the battery.
</p>
        </div>

        <div className="rounded-2xl border border-line bg-paper px-6 sm:px-8">
          <Accordion type="single" collapsible defaultValue="item-0">
            {PASSPORT_FLOW.map((item, i) => (
              <AccordionItem key={item.title} value={`item-${i}`}>
                <AccordionTrigger>{item.title}</AccordionTrigger>
                <AccordionContent>{item.body}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </div>
    </Shell>
  );
}

/* ===================================================================== cta */

export function CallToAction() {
  return (
    <Shell>
      <div className="rounded-[26px] border border-line bg-mist/70 px-8 py-16 text-center sm:px-12 sm:py-20">
        <h2 className="font-display mx-auto max-w-[18ch] text-[clamp(2rem,4.4vw,3.4rem)] leading-[1.02] font-bold text-balance">
          {CTA.title}
        </h2>
        <p className="mx-auto mt-5 max-w-[58ch] text-[14.5px] leading-relaxed text-ink-soft">
          {CTA.body}
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-2.5">
          <Button size="lg" asChild>
            <Link href={CTA.primary.href}>{CTA.primary.label}</Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <Link href={CTA.secondary.href}>
              {CTA.secondary.label}
              <ArrowUpRight />
            </Link>
          </Button>
        </div>
      </div>
    </Shell>
  );
}
