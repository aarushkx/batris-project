import { SOH_BANDS } from "@/lib/constants";

export const EM_DASH = "\u2014";

export function fmtPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return EM_DASH;
  return `${value.toFixed(digits)}%`;
}

export function fmtNumber(
  value: number | null | undefined,
  digits = 2,
  suffix = "",
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return EM_DASH;
  return `${value.toFixed(digits)}${suffix}`;
}

export function fmtSigned(value: number, digits = 2): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

export type Tone = "good" | "warn" | "bad" | "signal" | "estimated" | "default";

export function sohTone(soh: number): Tone {
  if (soh >= SOH_BANDS.healthy) return "good";
  if (soh >= SOH_BANDS.degraded) return "warn";
  return "bad";
}

export function riskTone(band: string): Tone {
  if (band === "LOW") return "good";
  if (band === "MODERATE") return "warn";
  return "bad";
}

export function severityTone(severity: string): Tone {
  if (severity === "none") return "good";
  if (severity === "critical") return "bad";
  return "warn";
}

export function confidenceTone(confidence: string): Tone {
  if (confidence === "HIGH") return "good";
  if (confidence === "MEDIUM") return "warn";
  return "default";
}

/** Risk drivers are ranked by how much they add to the score, not by name. */
export function driverTone(contribution: number): "urgent" | "advised" | "routine" {
  if (contribution >= 45) return "urgent";
  if (contribution >= 20) return "advised";
  return "routine";
}

export function humanise(token: string): string {
  return token.replace(/_/g, " ");
}

export function downloadJSON(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
