"use client";

import * as React from "react";
import { CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import {
  Finding,
  KeyValue,
  KeyValueGrid,
  Note,
} from "@/components/shared/primitives";
import { EM_DASH, driverTone, fmtSigned, humanise } from "@/lib/format";
import { RECOMMENDATION_ORDER } from "@/lib/constants";
import type {
  AnomalySummary,
  ChargingEnvelope,
  DegradationFactor,
  Recommendation,
  RiskDriver,
  UnavailableAnalysis,
  VerifyResult,
} from "@/lib/types";
import { cn } from "@/lib/utils";

/* -------------------------------------------------------------- factors --- */

export function DegradationFactors({ factors }: { factors: DegradationFactor[] }) {
  if (!factors.length) return <Note>No attributable degradation factors returned.</Note>;

  const max = Math.max(
    ...factors.map((f) => Math.abs(f.impact_soh_percentage_points)),
    0.01,
  );

  return (
    <div className="grid gap-2.5">
      {factors.map((f) => {
        const impact = f.impact_soh_percentage_points;
        const negative = impact < 0;
        const width = (Math.abs(impact) / max) * 100;
        return (
          <div key={f.factor} className="rounded-lg border border-line bg-mist/50 p-4">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-[13.5px] font-semibold">{f.label}</span>
              <span
                className={cn(
                  "tabular text-[13px] font-semibold whitespace-nowrap",
                  negative ? "text-bad" : "text-good",
                )}
              >
                {fmtSigned(impact)} SOH pts
              </span>
            </div>
            <div className="mt-2.5 h-[5px] w-full overflow-hidden rounded-full bg-line">
              <div
                className={cn("h-full rounded-full", negative ? "bg-bad" : "bg-good")}
                style={{ width: `${width}%` }}
              />
            </div>
            <p className="mt-2.5 text-[12px] leading-relaxed text-ink-soft">
              {f.mechanism}
            </p>
            {f.top_signals?.length ? (
              <div className="mt-2.5 flex flex-wrap gap-x-5 gap-y-1 text-[11.5px] text-ink-soft">
                {f.top_signals.map((s) => (
                  <span key={s.feature} className="tabular">
                    {s.signal}:{" "}
                    <span className="text-ink">
                      {s.measured_value === null ? "n/a" : s.measured_value}
                    </span>
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

/* --------------------------------------------------------------- safety --- */

export function RiskDrivers({ drivers }: { drivers: RiskDriver[] }) {
  if (!drivers.length) return <Note>No elevated risk factors detected.</Note>;
  return (
    <div className="grid gap-1">
      {drivers.map((d) => (
        <Finding
          key={d.factor}
          tone={driverTone(d.contribution)}
          tags={[{ label: humanise(d.factor) }]}
          action={`+${d.contribution.toFixed(0)} risk`}
          why={d.finding}
        />
      ))}
    </div>
  );
}

export function ChargingEnvelopeGrid({ envelope }: { envelope: ChargingEnvelope }) {
  const e = envelope;
  return (
    <KeyValueGrid min={150}>
      <KeyValue label="Max charge current" value={`${e.max_charge_current_a} A`} />
      <KeyValue label="Max charge rate" value={`${e.max_charge_c_rate}C`} />
      <KeyValue
        label="Derating applied"
        value={`${(100 * e.derating_applied).toFixed(0)}%`}
      />
      <KeyValue
        label="SOC window"
        value={`${e.recommended_soc_window_percent[0]}\u2013${e.recommended_soc_window_percent[1]}%`}
      />
      <KeyValue
        label="CV setpoint"
        value={
          e.charge_voltage_setpoint_v ? `${e.charge_voltage_setpoint_v} V` : EM_DASH
        }
      />
      <KeyValue
        label="Charge temp window"
        value={`${e.charge_temperature_window_c[0]}\u2013${e.charge_temperature_window_c[1]} \u00b0C`}
      />
    </KeyValueGrid>
  );
}

export function Recommendations({ items }: { items: Recommendation[] }) {
  const sorted = React.useMemo(
    () =>
      [...items].sort(
        (a, b) => RECOMMENDATION_ORDER[a.priority] - RECOMMENDATION_ORDER[b.priority],
      ),
    [items],
  );
  if (!sorted.length) return <Note>No recommendations returned.</Note>;
  return (
    <div className="grid gap-1">
      {sorted.map((r, i) => (
        <Finding
          key={`${r.category}-${i}`}
          tone={r.priority}
          tags={[
            { label: r.priority, tone: r.priority },
            { label: r.category },
          ]}
          action={r.action}
          why={r.rationale}
        />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------- anomalies --- */

export function AnomalyList({
  anomaly,
  emptyNote,
}: {
  anomaly: AnomalySummary;
  emptyNote?: string;
}) {
  if (!anomaly.anomalies.length) {
    return (
      <Note>
        {emptyNote ??
          "No anomalies detected on this cycle. Normal capacity fade is expected behaviour and is not flagged as an anomaly."}
      </Note>
    );
  }
  return (
    <div className="grid gap-1">
      {anomaly.anomalies.map((x, i) => (
        <Finding
          key={`${x.code}-${i}`}
          tone={x.severity}
          tags={[
            { label: x.severity, tone: x.severity as "critical" | "warning" | "info" },
            { label: x.source },
          ]}
          action={x.code}
          why={x.detail}
        />
      ))}
    </div>
  );
}

export function DetectorCoverage({
  detectors,
}: {
  detectors: Record<string, boolean>;
}) {
  const entries = Object.entries(detectors ?? {});
  if (!entries.length) return null;
  return (
    <div className="mt-4 flex flex-wrap gap-2">
      {entries.map(([name, ran]) => (
        <span
          key={name}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
            ran
              ? "border-good/30 bg-good/8 text-good"
              : "border-line bg-mist text-ink-soft line-through decoration-ink-soft/40",
          )}
        >
          {ran ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3" />}
          {humanise(name)}
        </span>
      ))}
    </div>
  );
}

export function UnavailableAnalyses({ items }: { items: UnavailableAnalysis[] }) {
  return (
    <div className="grid gap-1">
      {items.map((u) => (
        <Finding
          key={u.analysis}
          tone="info"
          tags={[{ label: "unavailable" }]}
          action={u.analysis}
          why={
            <>
              {u.reason}
              <div className="mt-1">
                <span className="font-semibold text-ink">To enable: </span>
                {u.how_to_enable}
              </div>
            </>
          }
        />
      ))}
    </div>
  );
}

/* ---------------------------------------------------------- verification --- */

export function VerifyBox({
  result,
  context,
}: {
  result: VerifyResult;
  context?: string;
}) {
  const ok = result.valid;
  return (
    <div
      className={cn(
        "rounded-lg border p-4 text-[12.5px]",
        ok ? "border-good/35 bg-good/6" : "border-bad/35 bg-bad/6",
      )}
    >
      <div
        className={cn(
          "flex items-center gap-2 text-[13.5px] font-semibold",
          ok ? "text-good" : "text-bad",
        )}
      >
        {ok ? <CheckCircle2 className="size-4" /> : <ShieldAlert className="size-4" />}
        {ok ? "Signature valid" : "Signature invalid"}
      </div>
      {context ? <p className="mt-1.5 leading-relaxed text-ink-soft">{context}</p> : null}
      <ul className="mt-2.5 space-y-1 text-ink-soft">
        {ok ? (
          <>
            {result.trust_anchor && <li>Trust anchor: {result.trust_anchor}</li>}
            {result.public_key_fingerprint && (
              <li className="break-all">
                Key fingerprint: <Mono>{result.public_key_fingerprint}</Mono>
              </li>
            )}
            {result.passport_id && (
              <li className="break-all">
                Passport ID: <Mono>{result.passport_id}</Mono>
              </li>
            )}
            {result.health_method && (
              <li>
                Health method:{" "}
                <span className="font-semibold text-ink">{result.health_method}</span>
              </li>
            )}
            {result.certified_test_status && (
              <li>
                Certified test:{" "}
                <span className="font-semibold text-ink">
                  {result.certified_test_status}
                </span>
              </li>
            )}
          </>
        ) : (
          (result.errors ?? []).map((e) => <li key={e}>{e}</li>)
        )}
        {(result.warnings ?? []).map((w) => (
          <li key={w} className="text-warn">
            {w}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Mono({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded border border-line bg-mist px-1.5 py-0.5 font-mono text-[11px]">
      {children}
    </code>
  );
}

export function JsonBlock({ data }: { data: unknown }) {
  return (
    <pre className="max-h-[420px] overflow-auto rounded-lg border border-line bg-ink p-4 font-mono text-[11px] leading-relaxed break-words whitespace-pre-wrap text-[#c9d3cd]">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
