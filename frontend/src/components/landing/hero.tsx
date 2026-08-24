import Link from "next/link";
import { ArrowUpRight, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HERO, HERO_STATS } from "@/lib/constants";

/**
 * Signature element.
 *
 * A real capacity-fade curve with the model's 90% band drawn around it and the
 * 80% end-of-first-life line crossing it. It is the product's whole argument in
 * one picture: the estimate is a band, not a point, and the decision it feeds is
 * a threshold crossing. Everything else on the page is kept quiet so this reads.
 */
function FadeCurve() {
  const width = 760;
  const height = 300;
  const pad = { l: 46, r: 20, t: 22, b: 34 };
  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;

  // Synthetic but physically shaped: slow linear fade, then an ageing knee.
  const points = Array.from({ length: 61 }, (_, i) => {
    const t = i / 60;
    const soh = 1.0 - 0.14 * t - 0.2 * Math.pow(Math.max(0, t - 0.62) / 0.38, 2.1);
    return { t, soh };
  });

  const x = (t: number) => pad.l + t * iw;
  const y = (v: number) => pad.t + (1 - (v - 0.6) / 0.45) * ih;

  const band = 0.035;
  const line = points.map((p) => `${x(p.t).toFixed(1)},${y(p.soh).toFixed(1)}`).join(" ");
  const upper = points.map((p) => `${x(p.t).toFixed(1)},${y(p.soh + band).toFixed(1)}`);
  const lower = points
    .map((p) => `${x(p.t).toFixed(1)},${y(p.soh - band).toFixed(1)}`)
    .reverse();

  const crossing = points.find((p) => p.soh <= 0.8) ?? points[points.length - 1];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      role="img"
      aria-label="Estimated capacity fade with a 90 percent confidence band crossing the 80 percent end-of-life threshold"
    >
      {[1.0, 0.9, 0.8, 0.7, 0.6].map((v) => (
        <g key={v}>
          <line
            x1={pad.l}
            y1={y(v)}
            x2={width - pad.r}
            y2={y(v)}
            stroke="var(--line)"
            strokeWidth={1}
          />
          <text
            x={pad.l - 10}
            y={y(v) + 4}
            fontSize={11}
            fill="var(--ink-soft)"
            textAnchor="end"
          >
            {Math.round(v * 100)}%
          </text>
        </g>
      ))}

      <polygon points={[...upper, ...lower].join(" ")} fill="var(--estimated)" opacity={0.14} />

      <line
        x1={pad.l}
        y1={y(0.8)}
        x2={width - pad.r}
        y2={y(0.8)}
        stroke="var(--ink)"
        strokeWidth={1.3}
        strokeDasharray="6 5"
        opacity={0.55}
      />

      <polyline
        points={line}
        fill="none"
        stroke="var(--estimated)"
        strokeWidth={2.4}
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ strokeDasharray: 1400, ["--dash" as string]: 1400 }}
        className="animate-draw"
      />

      <circle cx={x(crossing.t)} cy={y(crossing.soh)} r={5.5} fill="var(--paper)" />
      <circle
        cx={x(crossing.t)}
        cy={y(crossing.soh)}
        r={5.5}
        fill="none"
        stroke="var(--estimated)"
        strokeWidth={2.2}
      />

      <text
        x={pad.l + 4}
        y={y(0.8) - 9}
        fontSize={11}
        fill="var(--ink-soft)"
        fontWeight={600}
      >
        80% end of first life
      </text>
      <text
        x={width - pad.r}
        y={height - 8}
        fontSize={11}
        fill="var(--ink-soft)"
        textAnchor="end"
      >
        Cycles
      </text>
    </svg>
  );
}

export function Hero() {
  return (
    <section className="px-0 pt-3 sm:px-5">
      <div className="relative mx-auto max-w-[1320px] overflow-hidden rounded-[26px] border border-line bg-mist/60">
        <div className="grid-paper pointer-events-none absolute inset-0 opacity-45 mask-fade-b" />

        <div className="relative px-5 pt-16 pb-10 text-center sm:px-10 sm:pt-24">
          <span className="eyebrow inline-flex items-center gap-2 rounded-full border border-line bg-paper px-3.5 py-1.5">
            <span className="size-1.5 rounded-full bg-estimated" />
            {HERO.eyebrow}
          </span>

          <h1 className="font-display mx-auto mt-7 max-w-[16ch] text-[clamp(2.6rem,7.4vw,5.4rem)] leading-[0.98] font-bold text-balance">
            {HERO.headlineTop}
            <br />
            {HERO.headlineBottom}
          </h1>

          <p className="mx-auto mt-6 max-w-[62ch] text-[15px] leading-relaxed text-ink-soft">
            {HERO.body}
          </p>

          <div className="mt-8 flex flex-wrap justify-center gap-2.5">
            <Button size="lg" asChild>
              <Link href={HERO.primaryCta.href}>{HERO.primaryCta.label}</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href={HERO.secondaryCta.href}>
                {HERO.secondaryCta.label}
                <ArrowUpRight />
              </Link>
            </Button>
          </div>
        </div>

        {/* --------------------------------------------------- the visual */}
        <div className="relative px-4 pb-4 sm:px-8 sm:pb-8">
          <div className="relative rounded-[20px] border border-line bg-paper p-5 sm:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <span className="eyebrow">Estimated state of health</span>
                <div className="font-display mt-1 flex items-baseline gap-2 text-[44px] leading-none font-bold tabular">
                  78.4<span className="text-[26px] text-ink-soft">%</span>
                </div>
                <p className="mt-1.5 text-[12.5px] text-ink-soft tabular">
                  90% interval 74.9–81.9% · 1.57 Ah remaining
                </p>
              </div>

              <div className="flex flex-wrap gap-2.5">
                <div className="rounded-xl border border-line bg-mist/70 px-4 py-3">
                  <span className="eyebrow">Second-life grade</span>
                  <div className="font-display mt-0.5 text-[22px] font-bold">B</div>
                  <span className="text-[11.5px] text-ink-soft">
                    Stationary storage
                  </span>
                </div>
                <div className="rounded-xl border border-good/25 bg-good/8 px-4 py-3">
                  <span className="eyebrow text-good">Passport</span>
                  <div className="mt-1 flex items-center gap-1.5 text-[13.5px] font-semibold text-good">
                    <ShieldCheck className="size-4" />
                    Signature valid
                  </div>
                  <span className="text-[11.5px] text-ink-soft">
                    Ed25519 · issuer key
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-6">
              <FadeCurve />
            </div>

            <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-[11.5px] text-ink-soft">
              <span className="inline-flex items-center gap-2">
                <span className="h-[3px] w-4 rounded-full bg-estimated" />
                Estimated SOH
              </span>
              <span className="inline-flex items-center gap-2">
                <span className="h-2.5 w-4 rounded-sm bg-estimated/20" />
                90% confidence band
              </span>
              <span className="inline-flex items-center gap-2">
                <span className="h-[3px] w-4 rounded-full bg-ink/55" />
                End of first life
              </span>
            </div>
          </div>
        </div>

        {/* --------------------------------------------------- stat strip */}
        <div className="relative grid divide-y divide-line border-t border-line sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {HERO_STATS.map((stat) => (
            <div key={stat.label} className="px-6 py-6 text-center sm:px-8">
              <div className="font-display text-[30px] leading-none font-bold tabular">
                {stat.value}
                <span className="ml-1.5 text-[13px] font-medium text-ink-soft">
                  {stat.unit}
                </span>
              </div>
              <div className="mt-2 text-[12.5px] text-ink-soft">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
