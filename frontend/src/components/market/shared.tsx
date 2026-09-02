import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { REUSE_GRADES } from "@/lib/constants";
import { EM_DASH } from "@/lib/format";
import { cn } from "@/lib/utils";

type GradeMeta = (typeof REUSE_GRADES)[number];

/** Look up the published meaning of a reuse grade. */
export function gradeMeta(grade: string | null | undefined): GradeMeta | null {
  if (!grade) return null;
  return REUSE_GRADES.find((entry) => entry.value === grade.toUpperCase()) ?? null;
}

const GRADE_BADGE: Record<string, React.ComponentProps<typeof Badge>["variant"]> = {
  A: "good",
  B: "signal",
  C: "warn",
  RECYCLE: "bad",
};

export function GradeBadge({
  grade,
  className,
}: {
  grade: string | null | undefined;
  className?: string;
}) {
  const meta = gradeMeta(grade);
  if (!meta) {
    return (
      <Badge variant="default" className={className}>
        Not graded
      </Badge>
    );
  }
  return (
    <Badge variant={GRADE_BADGE[meta.value] ?? "default"} className={className}>
      {meta.label}
    </Badge>
  );
}

/** Risk band → badge tone, matching the dashboard's riskTone(). */
export function riskBadgeVariant(
  band: string | null | undefined,
): React.ComponentProps<typeof Badge>["variant"] {
  if (band === "LOW") return "good";
  if (band === "MODERATE") return "warn";
  if (!band) return "default";
  return "bad";
}

/**
 * A small boxed figure, used for the retained-SOH / capacity / energy / risk
 * grid on a listing card. Deliberately the same visual language as the
 * dashboard's KeyValue so a buyer reads one interface, not two.
 */
export function ListingStat({
  label,
  value,
  sub,
  icon,
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-lg border border-line bg-mist/50 px-3 py-2.5", className)}>
      <div className="eyebrow flex items-center gap-1.5">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-1 text-[17px] leading-tight font-semibold tabular">
        {value ?? EM_DASH}
      </div>
      {sub ? (
        <div className="mt-0.5 text-[10.5px] leading-snug text-ink-soft">{sub}</div>
      ) : null}
    </div>
  );
}

export function formatEnergy(wh: number | null | undefined): string {
  if (wh == null || !Number.isFinite(wh)) return EM_DASH;
  if (wh >= 1000) return `${(wh / 1000).toFixed(2)} kWh`;
  return `${wh.toFixed(wh < 100 ? 1 : 0)} Wh`;
}

export function formatCapacity(ah: number | null | undefined): string {
  if (ah == null || !Number.isFinite(ah)) return EM_DASH;
  return `${ah.toFixed(ah < 10 ? 2 : 1)} Ah`;
}

export function formatListingDate(value: string | null | undefined): string {
  if (!value) return EM_DASH;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Chemistry codes are acronyms and should stay uppercase. */
export function formatChemistry(chemistry: string | null | undefined): string {
  return (chemistry || "OTHER").toUpperCase();
}

export function formatFormFactor(formFactor: string | null | undefined): string {
  if (!formFactor) return "";
  return formFactor.replace(/_/g, " ");
}
