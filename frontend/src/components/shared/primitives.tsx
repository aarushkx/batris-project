import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { EM_DASH, type Tone } from "@/lib/format";

/* ==========================================================================
   Estimate rail
   --------------------------------------------------------------------------
   The signature element of this interface. Wherever a modelled number is
   shown, the 90% interval is drawn underneath it to scale, with the
   end-of-life threshold marked on the same axis. The point of the whole
   platform is that an estimate is not a measurement, so the uncertainty is
   given the same visual weight as the number itself rather than being
   demoted to a parenthesis.
   ========================================================================== */

export function EstimateRail({
  value,
  lower,
  upper,
  min = 0.5,
  max = 1.0,
  threshold,
  className,
}: {
  value: number;
  lower: number;
  upper: number;
  min?: number;
  max?: number;
  threshold?: number;
  className?: string;
}) {
  const span = Math.max(max - min, 1e-6);
  const pos = (v: number) => `${Math.min(100, Math.max(0, ((v - min) / span) * 100))}%`;
  const width = `${Math.min(100, Math.max(1.5, ((upper - lower) / span) * 100))}%`;

  return (
    <div className={cn("mt-3", className)}>
      <div className="relative h-[7px] w-full rounded-full bg-mist">
        <div
          className="absolute inset-y-0 rounded-full bg-estimated/25"
          style={{ left: pos(lower), width }}
        />
        <div
          className="absolute top-1/2 h-[15px] w-[2.5px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-estimated"
          style={{ left: pos(value) }}
        />
        {threshold !== undefined && threshold > min && threshold < max && (
          <div
            className="absolute top-1/2 h-[13px] w-px -translate-x-1/2 -translate-y-1/2 bg-ink-soft/70"
            style={{ left: pos(threshold) }}
          />
        )}
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] tabular text-ink-soft/70">
        <span>{Math.round(min * 100)}%</span>
        {threshold !== undefined && <span>EOL {Math.round(threshold * 100)}%</span>}
        <span>{Math.round(max * 100)}%</span>
      </div>
    </div>
  );
}

/* ========================================================================== */

const toneBadge: Record<Tone, React.ComponentProps<typeof Badge>["variant"]> = {
  good: "good",
  warn: "warn",
  bad: "bad",
  signal: "signal",
  estimated: "estimated",
  default: "default",
};

export function MetricCard({
  label,
  value,
  sub,
  pill,
  pillTone = "default",
  method,
  children,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  pill?: string;
  pillTone?: Tone;
  method?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col rounded-xl border border-line bg-card p-5">
      <span className="eyebrow">{label}</span>
      <div className="font-display mt-2 text-[38px] leading-[1.05] font-semibold tabular">
        {value}
      </div>
      {children}
      {sub ? (
        <p className="mt-2 text-[12.5px] leading-snug text-ink-soft">{sub}</p>
      ) : null}
      <div className="mt-auto flex flex-wrap items-center gap-2 pt-3">
        {pill ? <Badge variant={toneBadge[pillTone]}>{pill}</Badge> : null}
        {method ? (
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-estimated">
            {method}
          </span>
        ) : null}
      </div>
    </div>
  );
}

/* ========================================================================== */

export function KeyValue({
  label,
  value,
  tag,
  small,
}: {
  label: string;
  value: React.ReactNode;
  tag?: string;
  small?: boolean;
}) {
  return (
    <div className="rounded-lg border border-line bg-mist/60 px-3.5 py-2.5">
      <div className="eyebrow flex items-center gap-1.5">
        <span>{label}</span>
        {tag ? (
          <span className="text-estimated/90 tracking-[0.12em]">· {tag}</span>
        ) : null}
      </div>
      <div
        className={cn(
          "mt-1 tabular",
          small ? "text-[12.5px] leading-snug font-normal break-words" : "text-[16px] font-semibold",
        )}
      >
        {value ?? EM_DASH}
      </div>
    </div>
  );
}

export function KeyValueGrid({
  children,
  min = 180,
}: {
  children: React.ReactNode;
  min?: number;
}) {
  return (
    <div
      className="grid gap-2.5"
      style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${min}px, 1fr))` }}
    >
      {children}
    </div>
  );
}

/* ==========================================================================
   Finding row — one recommendation, risk driver, anomaly or unavailable
   analysis. A single component because they are the same object to the
   reader: a labelled claim with a reason underneath.
   ========================================================================== */

const accent: Record<string, string> = {
  urgent: "border-l-bad",
  critical: "border-l-critical",
  advised: "border-l-warn",
  warning: "border-l-warn",
  routine: "border-l-signal",
  info: "border-l-line",
  none: "border-l-line",
};

export function Finding({
  tags,
  action,
  why,
  extra,
  tone = "info",
}: {
  tags: { label: string; tone?: "urgent" | "advised" | "routine" | "critical" | "warning" | "info" | "plain" }[];
  action?: React.ReactNode;
  why?: React.ReactNode;
  extra?: React.ReactNode;
  tone?: string;
}) {
  return (
    <div className={cn("border-l-2 py-2.5 pl-3.5", accent[tone] ?? "border-l-line")}>
      <div className="flex flex-wrap items-center gap-1.5">
        {tags.map((t) => (
          <span
            key={t.label}
            className={cn(
              "rounded border border-line bg-mist px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-[0.1em] text-ink-soft",
              (t.tone === "urgent" || t.tone === "critical") && "border-bad/35 text-bad",
              (t.tone === "advised" || t.tone === "warning") && "border-warn/40 text-warn",
              t.tone === "routine" && "border-signal/30 text-signal",
            )}
          >
            {t.label}
          </span>
        ))}
      </div>
      {action ? (
        <div className="mt-1.5 text-[13px] font-medium leading-snug">{action}</div>
      ) : null}
      {why ? (
        <div className="mt-1 text-[12px] leading-relaxed text-ink-soft">{why}</div>
      ) : null}
      {extra}
    </div>
  );
}

/* ========================================================================== */

export function Note({ children }: { children: React.ReactNode }) {
  return <p className="text-[12.5px] leading-relaxed text-ink-soft">{children}</p>;
}

export function Caveat({ children }: { children: React.ReactNode }) {
  if (!children) return null;
  return (
    <p className="mt-4 border-t border-dashed border-line pt-3 text-[11.5px] leading-relaxed text-ink-soft italic">
      {children}
    </p>
  );
}

export function SectionCard({
  title,
  description,
  children,
  aside,
  id,
  className,
}: {
  title: string;
  description?: React.ReactNode;
  children: React.ReactNode;
  aside?: React.ReactNode;
  id?: string;
  className?: string;
}) {
  return (
    <section
      id={id}
      className={cn("rounded-xl border border-line bg-card p-5 sm:p-6", className)}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold tracking-[-0.01em]">{title}</h2>
          {description ? (
            <div className="mt-1.5 max-w-3xl text-[12.5px] leading-relaxed text-ink-soft">
              {description}
            </div>
          ) : null}
        </div>
        {aside}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function SubHeading({ children }: { children: React.ReactNode }) {
  return <h3 className="eyebrow mt-5 mb-2.5 first:mt-0">{children}</h3>;
}
