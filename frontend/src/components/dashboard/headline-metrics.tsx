"use client";

import { EstimateRail, MetricCard } from "@/components/shared/primitives";
import { METHOD_TAG_ESTIMATED } from "@/lib/constants";
import {
  EM_DASH,
  confidenceTone,
  fmtPct,
  riskTone,
  severityTone,
  sohTone,
} from "@/lib/format";
import type { AnomalySummary, HealthEstimate, SafetyAssessment, SecondLife } from "@/lib/types";

export function HeadlineMetrics({
  health,
  safety,
  anomaly,
  secondLife,
  anomalySub,
  eolThreshold,
}: {
  health: HealthEstimate;
  safety: SafetyAssessment;
  anomaly: AnomalySummary;
  secondLife: SecondLife;
  anomalySub: string;
  eolThreshold: number;
}) {
  const [lo, hi] = health.confidence_interval_90;

  // The rail is scaled to a window around the interval so the width of the
  // uncertainty is legible rather than being squashed into a full 0–100 axis.
  const railMin = Math.max(0, Math.min(lo, eolThreshold) - 0.12);
  const railMax = Math.min(1.05, Math.max(hi, eolThreshold) + 0.08);

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label="Estimated state of health"
        value={fmtPct(health.soh_percent)}
        sub={
          <>
            90% interval {(100 * lo).toFixed(1)}
            {"\u2013"}
            {(100 * hi).toFixed(1)}% · {health.remaining_capacity_ah} Ah remaining
            {health.fade_rate_soh_points_per_100_cycles != null ? (
              <>
                {" "}
                · fading {health.fade_rate_soh_points_per_100_cycles} pts/100 cycles
              </>
            ) : null}
          </>
        }
        pill={health.state_of_health_label}
        pillTone={sohTone(health.soh)}
        method={METHOD_TAG_ESTIMATED}
      >
        <EstimateRail
          value={health.soh}
          lower={lo}
          upper={hi}
          min={railMin}
          max={railMax}
          threshold={eolThreshold}
        />
      </MetricCard>

      <MetricCard
        label="Safety risk"
        value={safety.risk_score.toFixed(0)}
        sub={safety.band_meaning}
        pill={safety.risk_band}
        pillTone={riskTone(safety.risk_band)}
      />

      <MetricCard
        label="Anomaly status"
        value={anomaly.n_anomalies === 0 ? "Clear" : anomaly.n_anomalies}
        sub={anomalySub}
        pill={anomaly.max_severity.toUpperCase()}
        pillTone={severityTone(anomaly.max_severity)}
      />

      <MetricCard
        label="Second-life grade"
        value={secondLife.grade === "NOT_GRADED" ? EM_DASH : secondLife.grade}
        sub={secondLife.recommendation}
        pill={
          `${secondLife.grade_confidence} confidence` +
          (secondLife.grade_is_ambiguous && secondLife.worst_case_grade
            ? ` · could be ${secondLife.worst_case_grade}\u2013${secondLife.best_case_grade}`
            : "")
        }
        pillTone={confidenceTone(secondLife.grade_confidence)}
      />
    </div>
  );
}
