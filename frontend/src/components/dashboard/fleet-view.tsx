"use client";

import * as React from "react";
import { AlertTriangle, Gauge, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AnomalyList,
  ChargingEnvelopeGrid,
  DegradationFactors,
  Recommendations,
  RiskDrivers,
} from "@/components/shared/analysis";
import {
  Caveat,
  KeyValue,
  KeyValueGrid,
  SectionCard,
  SubHeading,
} from "@/components/shared/primitives";
import { HeadlineMetrics } from "@/components/dashboard/headline-metrics";
import { HealthTimeline } from "@/components/dashboard/health-timeline";
import { PublishListingPanel } from "@/components/market/publish-panel";
import { PassportPanel } from "@/components/dashboard/passport-panel";
import { TrajectoryChart } from "@/components/dashboard/trajectory-chart";
import { assessBattery, getBatteries, issuePassport } from "@/lib/api";
import {
  API_ERROR_HELP,
  DEFAULT_VARIANT,
  METHOD_TAG_ESTIMATED,
  METHOD_TAG_MEASURED,
  SOH_VARIANTS,
  type SohVariant,
} from "@/lib/constants";
import { EM_DASH, fmtPct } from "@/lib/format";
import type { Assessment, BatterySummary } from "@/lib/types";

export function FleetView() {
  const [batteries, setBatteries] = React.useState<BatterySummary[]>([]);
  const [batteryId, setBatteryId] = React.useState<string>("");
  const [cycle, setCycle] = React.useState<string>("");
  const [variant, setVariant] = React.useState<SohVariant>(DEFAULT_VARIANT);

  const [assessment, setAssessment] = React.useState<Assessment | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [assessing, setAssessing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // ---------------------------------------------------------------- load
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await getBatteries();
        if (cancelled) return;
        setBatteries(list);
        setBatteryId(list[0]?.battery_id ?? "");
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const run = React.useCallback(
    async (id: string, v: SohVariant, c: string) => {
      if (!id) return;
      setAssessing(true);
      setError(null);
      try {
        const parsed = c.trim() === "" ? null : Number(c);
        const result = await assessBattery(id, v, parsed);
        setAssessment(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setAssessing(false);
      }
    },
    [],
  );

  // Battery and variant changes re-assess immediately, as they did before.
  // The cycle box waits for Enter or the button, since it is typed into.
  React.useEffect(() => {
    if (batteryId) void run(batteryId, variant, cycle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batteryId, variant]);

  const issue = React.useCallback(() => {
    const parsed = cycle.trim() === "" ? null : Number(cycle);
    return issuePassport(batteryId, variant, parsed);
  }, [batteryId, variant, cycle]);

  const selected = batteries.find((b) => b.battery_id === batteryId);

  // ---------------------------------------------------------------- render
  return (
    <div className="grid gap-3">
      {/* ------------------------------------------------------- controls */}
      <div className="rounded-xl border border-line bg-card p-4 sm:p-5">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1.3fr_0.7fr_1.3fr_auto]">
          <div className="grid gap-1.5">
            <Label htmlFor="battery" className="eyebrow">
              Battery
            </Label>
            <Select value={batteryId} onValueChange={setBatteryId} disabled={loading}>
              <SelectTrigger id="battery">
                <SelectValue placeholder={loading ? "Loading\u2026" : "Select a battery"} />
              </SelectTrigger>
              <SelectContent>
                {batteries.map((b) => (
                  <SelectItem key={b.battery_id} value={b.battery_id}>
                    {b.battery_id} · {b.cycles} cycles
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="cycle" className="eyebrow">
              Assess at cycle
            </Label>
            <Input
              id="cycle"
              type="number"
              min={selected?.first_cycle ?? 1}
              max={selected?.last_cycle}
              value={cycle}
              placeholder="latest"
              onChange={(e) => setCycle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void run(batteryId, variant, cycle);
              }}
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="variant" className="eyebrow">
              Model
            </Label>
            <Select
              value={variant}
              onValueChange={(v) => setVariant(v as SohVariant)}
            >
              <SelectTrigger id="variant">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SOH_VARIANTS.map((v) => (
                  <SelectItem key={v.value} value={v.value}>
                    {v.label} · {v.hint}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-end">
            <Button
              className="w-full sm:w-auto"
              onClick={() => void run(batteryId, variant, cycle)}
              disabled={assessing || !batteryId}
            >
              {assessing ? (
                <RefreshCw className="animate-spin" />
              ) : (
                <Gauge />
              )}
              {assessing ? "Assessing\u2026" : "Assess"}
            </Button>
          </div>
        </div>

        <p className="mt-3 text-[12px] leading-relaxed text-ink-soft">
          {SOH_VARIANTS.find((v) => v.value === variant)?.description}
        </p>
      </div>

      {/* ---------------------------------------------------------- error */}
      {error ? (
        <Alert variant="bad">
          <AlertTriangle />
          <AlertTitle>{error}</AlertTitle>
          <AlertDescription>
            <p>If the trained models are missing, run these from the project root:</p>
            <pre className="mt-1 font-mono text-[11.5px] leading-relaxed">
              {API_ERROR_HELP.join("\n")}
            </pre>
          </AlertDescription>
        </Alert>
      ) : null}

      {/* -------------------------------------------------------- loading */}
      {loading || (!assessment && !error) ? (
        <div className="grid gap-3">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-44 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-72 rounded-xl" />
        </div>
      ) : null}

      {assessment ? (
        <FleetResults assessment={assessment} issue={issue} />
      ) : null}
    </div>
  );
}

/* ========================================================================== */

function FleetResults({
  assessment: a,
  issue,
}: {
  assessment: Assessment;
  issue: () => Promise<import("@/lib/types").Passport>;
}) {
  const ref = a.reference_measurement;

  return (
    <div className="grid gap-3">
      <HeadlineMetrics
        health={a.health}
        safety={a.safety}
        anomaly={a.anomaly}
        secondLife={a.second_life}
        eolThreshold={a.health.eol_threshold}
        anomalySub={`${a.anomaly.recent_anomalous_cycles ?? 0} of last ${
          a.anomaly.recent_window_cycles ?? 0
        } cycles flagged`}
      />

      {/* ------------------------------------------- reference comparison */}
      {ref ? (
        <SectionCard
          title="Estimate vs reference measurement"
          description="This benchmark dataset includes a real controlled-discharge capacity for every cycle, so the estimate can be checked against ground truth. A fielded battery would not have this column — obtaining it is exactly the expensive test this platform exists to avoid."
        >
          <KeyValueGrid>
            <KeyValue
              label="Estimated SOH"
              tag={METHOD_TAG_ESTIMATED.replace("Method: ", "")}
              value={fmtPct(a.health.soh_percent)}
            />
            <KeyValue
              label="Measured SOH"
              tag={METHOD_TAG_MEASURED.replace("Method: ", "")}
              value={fmtPct(100 * ref.measured_soh)}
            />
            <KeyValue
              label="Error"
              value={`${ref.estimation_error_percentage_points >= 0 ? "+" : ""}${ref.estimation_error_percentage_points.toFixed(2)} pts`}
            />
            <KeyValue
              label="Inside 90% interval"
              value={ref.within_confidence_interval ? "Yes" : "No"}
            />
          </KeyValueGrid>
        </SectionCard>
      ) : null}

      {/* ------------------------------------------------------ trajectory */}
      {a.trajectory ? (
        <SectionCard
          title="Degradation trajectory"
          description={`${a.battery_id} · ${a.total_cycles_observed} cycles observed · assessed at cycle ${a.cycle_index} · ${a.trajectory?.method ?? "XGBoost"}`}
        >
          <div className="mb-3 rounded-xl border border-ink/10 bg-ink/5 px-3 py-2 text-[12px] leading-5 text-ink-soft">
            <span className="font-semibold text-ink">Out-of-sample validation:</span>{" "}{a.trajectory.description}
          </div>
          <TrajectoryChart trajectory={a.trajectory} markCycle={a.cycle_index} />
        </SectionCard>
      ) : null}

      {/* -------------------------------------------------------- timeline */}
      <HealthTimeline assessment={a} id="timeline" />

      {/* --------------------------------------------------------- factors */}
      <SectionCard
        title="Why is this battery degrading?"
        description={a.degradation_summary}
      >
        <DegradationFactors factors={a.degradation_factors} />
        <Caveat>{a.explanation_caveat}</Caveat>
      </SectionCard>

      {/* ---------------------------------------------- safety + practice */}
      <div className="grid gap-3 lg:grid-cols-2">
        <SectionCard title="Safety assessment">
          <SubHeading>Risk drivers</SubHeading>
          <RiskDrivers drivers={a.safety.risk_drivers} />
          <SubHeading>Safe charging envelope</SubHeading>
          <ChargingEnvelopeGrid envelope={a.safety.safe_charging_envelope} />
        </SectionCard>

        <SectionCard title="Recommended practice">
          <Recommendations items={a.safety.recommendations} />
        </SectionCard>
      </div>

      {/* ------------------------------------------------------- anomalies */}
      <SectionCard title="Anomaly detections">
        <AnomalyList anomaly={a.anomaly} />
      </SectionCard>

      {/* ------------------------------------------------------- passport */}
      <PassportPanel
        id="passport"
        nextStep={a.second_life.next_step}
        issue={issue}
        allowTamper
      />

      {/* ---------------------------------------------------- second life */}
      <PublishListingPanel assessment={a} id="market" />

      {/* ------------------------------------------------------ provenance */}
      <SectionCard
        title="Model provenance"
        description="Everything needed to reproduce or audit the number above."
      >
        <KeyValueGrid>
          <KeyValue small label="SOH model variant" value={a.model_provenance.soh_model_variant} />
          <KeyValue small label="Features used" value={a.model_provenance.soh_features_used} />
          <KeyValue small label="Validation method" value={a.model_provenance.validation_method} />
          <KeyValue
            small
            label="Out-of-sample MAE"
            value={
              a.model_provenance.validation_mae_soh_points
                ? `${a.model_provenance.validation_mae_soh_points} SOH pts`
                : "see report"
            }
          />
          <KeyValue
            small
            label="Trained on"
            value={(a.model_provenance.training_batteries ?? []).join(", ") || EM_DASH}
          />
          <KeyValue small label="Training cycles" value={a.model_provenance.training_cycles ?? EM_DASH} />
          <KeyValue
            small
            label="Interval calibration"
            value={`${a.model_provenance.interval_calibration_factor}\u00d7`}
          />
          <KeyValue
            small
            label="Training data hash"
            value={a.model_provenance.training_data_sha256 ?? EM_DASH}
          />
        </KeyValueGrid>
      </SectionCard>
    </div>
  );
}
