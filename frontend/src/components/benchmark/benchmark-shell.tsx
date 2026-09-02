"use client";

import * as React from "react";
import { AlertTriangle, BarChart3, FlaskConical, Target, Trophy } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SectionCard } from "@/components/shared/primitives";
import { AccuracyPanel } from "@/components/benchmark/accuracy-panel";
import { TrajectoryChart } from "@/components/dashboard/trajectory-chart";
import { getBenchmarkResults } from "@/lib/api";
import type { BenchmarkModelResult, BenchmarkResults, Trajectory } from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n: number, dp = 2): string {
  return n.toFixed(dp);
}

function fmtSign(n: number, dp = 2): string {
  return (n >= 0 ? "+" : "") + n.toFixed(dp);
}

/** True when this model has the best (lowest) MAE. */
function isBest(model: BenchmarkModelResult, bestKey: string) {
  return model.model_key === bestKey;
}

// ---------------------------------------------------------------------------
// SVG Bar Chart — LOBO MAE Comparison
// ---------------------------------------------------------------------------

const CHART_COLORS = [
  "var(--ink-soft)",   // Mean Baseline
  "var(--ink)",        // Linear Regression
  "var(--good)",       // Random Forest
  "var(--warn)",       // Gradient Boosting
  "var(--signal)",     // SVR
  "var(--estimated)",  // XGBoost
];

function MaeBarChart({ models, bestKey }: { models: BenchmarkModelResult[]; bestKey: string }) {
  const W = 700;
  const H = 44 * models.length + 40;
  const left = 150;
  const right = 80;
  const barH = 26;
  const gap = 44;
  const maxVal = Math.max(...models.map((m) => m.overall.mae_soh_points)) * 1.15;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full max-w-[720px]"
      role="img"
      aria-label="LOBO MAE comparison bar chart"
    >
      {models.map((m, i) => {
        const y = 20 + i * gap;
        const barW = ((W - left - right) * m.overall.mae_soh_points) / maxVal;
        const best = isBest(m, bestKey);

        return (
          <g key={m.model_key}>
            <text
              x={left - 12}
              y={y + barH / 2}
              textAnchor="end"
              dominantBaseline="central"
              className="fill-ink text-[12px]"
              fontWeight={best ? 700 : 400}
            >
              {m.model_display_name}
            </text>
            <rect
              x={left}
              y={y}
              width={Math.max(barW, 2)}
              height={barH}
              rx={4}
              fill={best ? "var(--signal)" : CHART_COLORS[i % CHART_COLORS.length]}
              opacity={best ? 1 : 0.65}
            />
            <text
              x={left + barW + 8}
              y={y + barH / 2}
              dominantBaseline="central"
              className="fill-ink text-[11px] tabular"
              fontWeight={600}
            >
              {fmt(m.overall.mae_soh_points)}
            </text>
            {best && (
              <text
                x={left + barW + 48}
                y={y + barH / 2}
                dominantBaseline="central"
                className="fill-good text-[10px]"
                fontWeight={600}
              >
                ◀ BEST
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// SVG Grouped Bar Chart — Per-Battery MAE
// ---------------------------------------------------------------------------

function PerBatteryChart({
  models,
  batteries,
}: {
  models: BenchmarkModelResult[];
  batteries: string[];
}) {
  const W = 760;
  const topPad = 20;
  const bottomPad = 50;
  const leftPad = 56;
  const rightPad = 20;
  const groupW = (W - leftPad - rightPad) / batteries.length;
  const barW = Math.min(14, (groupW - 16) / models.length);
  const allVals = models.flatMap((m) => batteries.map((b) => m.per_battery[b]?.mae_soh_points ?? 0));
  const maxVal = Math.max(...allVals) * 1.15;
  const chartH = 220;
  const H = topPad + chartH + bottomPad;

  const yScale = (v: number) => topPad + chartH - (v / maxVal) * chartH;

  // Y-axis ticks
  const yTicks: number[] = [];
  const step = Math.ceil(maxVal / 5);
  for (let v = 0; v <= maxVal; v += step) yTicks.push(v);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Per-battery MAE comparison">
      {/* Grid lines */}
      {yTicks.map((v) => (
        <g key={v}>
          <line
            x1={leftPad}
            x2={W - rightPad}
            y1={yScale(v)}
            y2={yScale(v)}
            stroke="var(--line)"
            strokeWidth={1}
          />
          <text
            x={leftPad - 8}
            y={yScale(v)}
            textAnchor="end"
            dominantBaseline="central"
            className="fill-ink-soft text-[10px] tabular"
          >
            {v}
          </text>
        </g>
      ))}

      {/* Y-axis label */}
      <text
        x={14}
        y={topPad + chartH / 2}
        textAnchor="middle"
        dominantBaseline="central"
        transform={`rotate(-90, 14, ${topPad + chartH / 2})`}
        className="fill-ink-soft text-[10px]"
      >
        MAE (SOH pts)
      </text>

      {/* Bars */}
      {batteries.map((bat, bi) => {
        const groupX = leftPad + bi * groupW + groupW / 2;
        const totalBarsW = models.length * barW;
        const startX = groupX - totalBarsW / 2;

        return (
          <g key={bat}>
            {models.map((m, mi) => {
              const val = m.per_battery[bat]?.mae_soh_points ?? 0;
              const x = startX + mi * barW;
              const h = (val / maxVal) * chartH;
              return (
                <rect
                  key={m.model_key}
                  x={x}
                  y={yScale(val)}
                  width={barW - 1.5}
                  height={Math.max(h, 1)}
                  rx={2}
                  fill={CHART_COLORS[mi % CHART_COLORS.length]}
                  opacity={0.8}
                />
              );
            })}
            {/* Battery label */}
            <text
              x={groupX}
              y={topPad + chartH + 16}
              textAnchor="middle"
              className="fill-ink text-[11px]"
              fontWeight={500}
            >
              {bat}
            </text>
          </g>
        );
      })}

      {/* Legend */}
      {models.map((m, i) => {
        const lx = leftPad + i * 120;
        const ly = H - 12;
        return (
          <g key={m.model_key}>
            <rect x={lx} y={ly - 5} width={10} height={10} rx={2} fill={CHART_COLORS[i % CHART_COLORS.length]} opacity={0.8} />
            <text x={lx + 14} y={ly} dominantBaseline="central" className="fill-ink-soft text-[9px]">
              {m.model_display_name}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Trajectory Explorer — algorithm + battery dropdowns, independent state
// ---------------------------------------------------------------------------

function TrajectoryExplorer({
  models,
  batteries,
  bestKey,
}: {
  models: BenchmarkModelResult[];
  batteries: string[];
  bestKey: string;
}) {
  // Each dropdown owns its own state, so changing one never resets the other.
  const [modelKey, setModelKey] = React.useState<string>(bestKey);
  const [batteryId, setBatteryId] = React.useState<string>(batteries[0] ?? "");

  const model = models.find((m) => m.model_key === modelKey) ?? models[0];
  const stats = model?.per_battery[batteryId];
  const fold = model?.trajectories?.[batteryId];
  const best = model ? isBest(model, bestKey) : false;

  const controls = (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="grid gap-1.5">
        <Label htmlFor="benchAlgorithm" className="eyebrow">
          Algorithm
        </Label>
        <Select value={modelKey} onValueChange={setModelKey}>
          <SelectTrigger id="benchAlgorithm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {models.map((m) => (
              <SelectItem key={m.model_key} value={m.model_key}>
                {m.model_display_name} · {fmt(m.overall.mae_soh_points)} MAE
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="benchBattery" className="eyebrow">
          Battery
        </Label>
        <Select value={batteryId} onValueChange={setBatteryId}>
          <SelectTrigger id="benchBattery">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {batteries.map((b) => (
              <SelectItem key={b} value={b}>
                {b}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );

  if (!model || !fold) {
    return (
      <div className="grid gap-4">
        {controls}
        <Alert variant="warn">
          <AlertTriangle className="size-4" />
          <AlertTitle>Per-cycle curves not available</AlertTitle>
          <AlertDescription>
            This benchmark result was generated before per-cycle predictions were captured.
            Regenerate it with <code className="font-mono">python -m backend.batris.benchmark</code> to
            enable this chart.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const trajectory: Trajectory = {
    method: `LOBO ${model.model_display_name} (battery held out)`,
    description: `${batteryId} was excluded from training.`,
    cycle_index: fold.cycle_index,
    estimated_soh: fold.estimated_soh,
    measured_soh: fold.measured_soh,
    anomaly_score: [],
    anomalous_cycles: [],
    peak_temp_c: [],
  };

  return (
    <div className="grid gap-4">
      {controls}

      <div className="rounded-xl border border-line bg-mist/30 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-[14px] font-semibold text-ink">
              {batteryId}
              <span className="ml-2 font-normal text-ink-soft">
                held out — never seen by {model.model_display_name} during training
              </span>
            </p>
            {stats && (
              <p className="mt-0.5 text-[12.5px] tabular text-ink-soft">
                Out-of-sample MAE <span className="font-semibold text-ink">{fmt(stats.mae_soh_points)}</span>{" "}
                SOH points · R² <span className="font-semibold text-ink">{fmt(stats.r2, 3)}</span>
              </p>
            )}
          </div>
          {best && (
            <Badge variant="signal" className="text-[10.5px] px-1.5 py-0">
              Best model
            </Badge>
          )}
        </div>

        <div className="mt-4">
          <TrajectoryChart trajectory={trajectory} markCycle={-1} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Shell
// ---------------------------------------------------------------------------

export function BenchmarkShell() {
  const [data, setData] = React.useState<BenchmarkResults | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await getBenchmarkResults();
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-[1320px] px-5 py-10 sm:px-8">
        <Skeleton className="mb-4 h-10 w-64 rounded-lg" />
        <Skeleton className="mb-6 h-5 w-96 rounded-lg" />
        <div className="grid gap-3">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-[1320px] px-5 py-10 sm:px-8">
        <Alert variant="bad">
          <AlertTriangle className="size-4" />
          <AlertTitle>Benchmark not available</AlertTitle>
          <AlertDescription>
            <p className="mb-2">{error ?? "No data received."}</p>
            <p className="text-[13px] text-ink-soft">
              Generate the benchmark first:
            </p>
            <pre className="mt-2 rounded-lg bg-mist p-3 font-mono text-[12.5px]">
              python -m backend.batris.benchmark
            </pre>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const { models, batteries, best_model, best_model_display_name } = data;
  const bestModel = models.find((m) => m.model_key === best_model)!;

  return (
    <div className="mx-auto max-w-[1320px] px-5 py-10 sm:px-8">
      {/* ---------------------------------------------------------------- Hero */}
      <div className="mb-10">
        <p className="eyebrow mb-2">Model benchmark</p>
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
          Comparing candidate models
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
          Six candidate models evaluated under the same leave-one-battery-out
          cross-validation protocol. Each model is trained on all batteries
          except one and tested on the battery it has never seen — the same
          evaluation used throughout BATRIS.
        </p>

        <div className="mt-5 flex flex-wrap gap-3">
          <Badge variant="outline" className="gap-1.5 px-3 py-1.5 text-[12.5px]">
            <FlaskConical className="size-3.5" />
            {data.n_batteries} batteries · {data.n_cycles} cycles
          </Badge>
          <Badge variant="outline" className="gap-1.5 px-3 py-1.5 text-[12.5px]">
            <BarChart3 className="size-3.5" />
            {data.features_used} input features
          </Badge>
          <Badge variant="outline" className="gap-1.5 px-3 py-1.5 text-[12.5px]">
            <Trophy className="size-3.5" />
            Best: {best_model_display_name}
          </Badge>
          <a
            href="#accuracy"
            className="inline-flex items-center gap-1.5 rounded-full border border-ink bg-ink px-3 py-1.5 text-[12.5px] font-medium text-white transition-colors hover:bg-ink/88"
          >
            <Target className="size-3.5" />
            Jump to accuracy
          </a>
        </div>
      </div>

      {/* ------------------------------------------------------- Report sections */}
      <div className="grid gap-3">
        {/* -------------------------------------------------------- Accuracy */}
        <AccuracyPanel data={data} />

        {/* --------------------------------------------------- Overall table */}
        <SectionCard
          title="Overall LOBO results"
          description="All values in SOH percentage points. Lower MAE, RMSE, and max error are better. Higher R² is better. Bias near zero indicates an unbiased estimator."
        >
          <div className="overflow-hidden rounded-xl border border-line">
            <Table>
              <TableHeader>
                <TableRow className="bg-mist/50">
                  <TableHead>Model</TableHead>
                  <TableHead className="text-right">LOBO MAE ↓</TableHead>
                  <TableHead className="text-right">RMSE ↓</TableHead>
                  <TableHead className="text-right">R² ↑</TableHead>
                  <TableHead className="text-right">Max error ↓</TableHead>
                  <TableHead className="text-right">Mean bias</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {models.map((m) => {
                  const best = isBest(m, best_model);
                  return (
                    <TableRow key={m.model_key} className={best ? "bg-signal/5" : undefined}>
                      <TableCell className="font-medium text-ink">
                        <span className="flex items-center gap-2">
                          {m.model_display_name}
                          {best && (
                            <Badge variant="signal" className="text-[10.5px] px-1.5 py-0">
                              Best
                            </Badge>
                          )}
                        </span>
                      </TableCell>
                      <TableCell className={`text-right font-mono tabular ${best ? "font-bold text-signal" : "text-ink"}`}>
                        {fmt(m.overall.mae_soh_points)}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular text-ink">
                        {fmt(m.overall.rmse_soh_points)}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular text-ink">
                        {fmt(m.overall.r2, 3)}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular text-ink">
                        {fmt(m.overall.max_error_soh_points)}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular text-ink">
                        {fmtSign(m.overall.bias_soh_points)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </SectionCard>

        {/* ------------------------------------------------------- MAE bar chart */}
        <SectionCard
          title="LOBO MAE comparison"
          description="Leave-one-battery-out MAE (SOH percentage points) — lower is better."
        >
          <MaeBarChart models={models} bestKey={best_model} />
        </SectionCard>

        {/* -------------------------------------------------- Per-battery table */}
        <SectionCard
          title="Per-battery MAE breakdown"
          description="MAE in SOH percentage points per held-out battery. Bold green marks the best model for that battery."
        >
          <div className="overflow-hidden rounded-xl border border-line">
            <Table>
              <TableHeader>
                <TableRow className="bg-mist/50">
                  <TableHead>Model</TableHead>
                  {batteries.map((b) => (
                    <TableHead key={b} className="text-right">
                      {b}
                    </TableHead>
                  ))}
                  <TableHead className="text-right">Overall</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {models.map((m) => {
                  const best = isBest(m, best_model);
                  return (
                    <TableRow key={m.model_key} className={best ? "bg-signal/5" : undefined}>
                      <TableCell className="font-medium text-ink">
                        <span className="flex items-center gap-2">
                          {m.model_display_name}
                          {best && (
                            <Badge variant="signal" className="text-[10.5px] px-1.5 py-0">
                              Best
                            </Badge>
                          )}
                        </span>
                      </TableCell>
                      {batteries.map((b) => {
                        const val = m.per_battery[b]?.mae_soh_points;
                        // Highlight the best value per battery column
                        const colBest = Math.min(
                          ...models.map((mm) => mm.per_battery[b]?.mae_soh_points ?? Infinity)
                        );
                        const isColBest = val != null && Math.abs(val - colBest) < 0.005;
                        return (
                          <TableCell
                            key={b}
                            className={`text-right font-mono tabular ${
                              isColBest ? "font-bold text-good" : "text-ink"
                            }`}
                          >
                            {val != null ? fmt(val) : "—"}
                          </TableCell>
                        );
                      })}
                      <TableCell className={`text-right font-mono tabular ${best ? "font-bold text-signal" : "text-ink"}`}>
                        {fmt(m.overall.mae_soh_points)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </SectionCard>

        {/* ------------------------------------------------- Per-battery chart */}
        <SectionCard title="Per-battery MAE comparison">
          <PerBatteryChart models={models} batteries={batteries} />
        </SectionCard>

        {/* --------------------------------------------------- Trajectory explorer */}
        <SectionCard
          title="Measured vs. estimated SOH"
          description="Pick any algorithm and any held-out battery to see the curve predicted by a model that never saw that cell during training — the same leave-one-battery-out protocol used for every metric above."
        >
          <TrajectoryExplorer models={models} batteries={batteries} bestKey={best_model} />
        </SectionCard>

        {/* ----------------------------------------------- Conclusion */}
        <SectionCard title="Model selection">
          <div className="max-w-3xl space-y-3 text-[14px] leading-relaxed text-ink-soft">
            <p>
              We compared <strong className="text-ink">{models.length} candidate models</strong> using
              the same leave-one-battery-out validation protocol. Each model was tested on batteries
              it had never seen during training, and we compared their MAE, RMSE, R², maximum error,
              and bias.
            </p>
            <p>
              The <strong className="text-ink">{best_model_display_name}</strong> model achieved the
              lowest out-of-battery MAE of{" "}
              <strong className="font-mono tabular text-signal">
                {fmt(bestModel.overall.mae_soh_points)} SOH points
              </strong>
              {" "}with an R² of{" "}
              <strong className="font-mono tabular text-ink">
                {fmt(bestModel.overall.r2, 3)}
              </strong>
              , making it the strongest model for generalisation to unseen batteries.
            </p>
            <div className="rounded-lg border border-line bg-mist/50 p-4 text-[13.5px]">
              <p className="font-medium text-ink">
                &ldquo;We evaluated {models.length} candidate models using the same
                leave-one-battery-out validation protocol. Each model was tested on
                batteries it had never seen during training. We selected the model
                with the strongest out-of-battery performance based on unseen-battery
                MAE.&rdquo;
              </p>
            </div>
          </div>
        </SectionCard>

        {/* --------------------------------------------------- Methodology */}
        <SectionCard title="Methodology" className="bg-mist/30">
          <ul className="grid gap-2 text-[13px] leading-relaxed text-ink-soft sm:grid-cols-2">
            <li className="flex gap-2">
              <span className="mt-0.5 text-signal">●</span>
              Same {data.features_used} input features for every model
            </li>
            <li className="flex gap-2">
              <span className="mt-0.5 text-signal">●</span>
              Same leave-one-battery-out folds
            </li>
            <li className="flex gap-2">
              <span className="mt-0.5 text-signal">●</span>
              Train only on training batteries, predict only on held-out
            </li>
            <li className="flex gap-2">
              <span className="mt-0.5 text-signal">●</span>
              Same preprocessing for comparable models
            </li>
            <li className="flex gap-2">
              <span className="mt-0.5 text-signal">●</span>
              Same 5 evaluation metrics reported for all
            </li>
            <li className="flex gap-2">
              <span className="mt-0.5 text-signal">●</span>
              Performance reported per held-out battery, not only overall
            </li>
          </ul>
        </SectionCard>
      </div>
    </div>
  );
}
