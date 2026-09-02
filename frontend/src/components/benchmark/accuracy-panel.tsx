"use client";

import * as React from "react";
import { Info, Target } from "lucide-react";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SectionCard } from "@/components/shared/primitives";
import {
  accuracyForAll,
  errorHistogram,
  formatShare,
  type AccuracyReport,
} from "@/lib/accuracy";
import { ACCURACY_SECTION, ACCURACY_TOLERANCES } from "@/lib/constants";
import type { BenchmarkResults } from "@/lib/types";
import { cn } from "@/lib/utils";

/* ==========================================================================
   Parity plot — estimated against measured, with the ideal line
   --------------------------------------------------------------------------
   The single most honest way to show a regression's accuracy: every held-out
   prediction as a dot, and a diagonal showing where a perfect estimator would
   have put them. Spread away from the line *is* the error.
   ========================================================================== */

function ParityPlot({ report }: { report: AccuracyReport }) {
  const W = 520;
  const H = 420;
  const pad = { top: 16, right: 16, bottom: 44, left: 48 };
  const iw = W - pad.left - pad.right;
  const ih = H - pad.top - pad.bottom;

  const values = report.points.flatMap((point) => [point.measured, point.estimated]);
  const lo = Math.max(0, Math.floor((Math.min(...values) - 2) / 5) * 5);
  const hi = Math.min(105, Math.ceil((Math.max(...values) + 2) / 5) * 5);
  const span = Math.max(1, hi - lo);

  const sx = (value: number) => pad.left + ((value - lo) / span) * iw;
  const sy = (value: number) => pad.top + (1 - (value - lo) / span) * ih;

  const ticks = Array.from({ length: 5 }, (_, index) => lo + (index / 4) * span);

  // A ±5 point corridor makes the tolerance table legible on the plot itself.
  const corridor = 5;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full max-w-[560px]"
      role="img"
      aria-label="Estimated against measured state of health for held-out predictions"
    >
      {ticks.map((value) => (
        <g key={`grid-${value}`}>
          <line
            x1={pad.left}
            x2={pad.left + iw}
            y1={sy(value)}
            y2={sy(value)}
            stroke="var(--line)"
            strokeWidth={1}
          />
          <text
            x={pad.left - 8}
            y={sy(value) + 3.5}
            textAnchor="end"
            className="fill-ink-soft text-[10px] tabular"
          >
            {value.toFixed(0)}%
          </text>
          <text
            x={sx(value)}
            y={H - 24}
            textAnchor="middle"
            className="fill-ink-soft text-[10px] tabular"
          >
            {value.toFixed(0)}%
          </text>
        </g>
      ))}

      {/* ±5 point corridor */}
      <polygon
        points={[
          `${sx(lo)},${sy(Math.min(hi, lo + corridor))}`,
          `${sx(Math.max(lo, hi - corridor))},${sy(hi)}`,
          `${sx(hi)},${sy(hi)}`,
          `${sx(hi)},${sy(Math.max(lo, hi - corridor))}`,
          `${sx(Math.min(hi, lo + corridor))},${sy(lo)}`,
          `${sx(lo)},${sy(lo)}`,
        ].join(" ")}
        fill="var(--good)"
        fillOpacity={0.07}
      />

      {/* perfect-estimator diagonal */}
      <line
        x1={sx(lo)}
        y1={sy(lo)}
        x2={sx(hi)}
        y2={sy(hi)}
        stroke="var(--ink)"
        strokeWidth={1.2}
        strokeDasharray="5 4"
        opacity={0.55}
      />

      {report.points.map((point, index) => (
        <circle
          key={index}
          cx={sx(point.measured)}
          cy={sy(point.estimated)}
          r={2}
          fill="var(--estimated)"
          fillOpacity={0.4}
        />
      ))}

      <text
        x={pad.left + iw / 2}
        y={H - 6}
        textAnchor="middle"
        className="fill-ink-soft text-[10.5px]"
      >
        Measured SOH (reference discharge)
      </text>
      <text
        x={12}
        y={pad.top + ih / 2}
        textAnchor="middle"
        transform={`rotate(-90, 12, ${pad.top + ih / 2})`}
        className="fill-ink-soft text-[10.5px]"
      >
        Estimated SOH
      </text>
    </svg>
  );
}

/* ==========================================================================
   Error distribution
   ========================================================================== */

function ErrorDistribution({ report }: { report: AccuracyReport }) {
  const bins = errorHistogram(report.absErrors, 1, 10);
  if (bins.length === 0) return null;
  const peak = Math.max(...bins.map((bin) => bin.share));

  return (
    <div className="grid gap-1.5">
      {bins.map((bin, index) => {
        const last = index === bins.length - 1;
        const width = peak > 0 ? (bin.share / peak) * 100 : 0;
        return (
          <div key={bin.from} className="flex items-center gap-3">
            <span className="w-20 shrink-0 text-right text-[11px] tabular text-ink-soft">
              {last ? `${bin.from}+ pts` : `${bin.from}\u2013${bin.to} pts`}
            </span>
            <div className="h-4 min-w-0 flex-1 overflow-hidden rounded bg-mist">
              <div
                className={cn(
                  "h-full rounded",
                  bin.from < 3 ? "bg-good/70" : bin.from < 5 ? "bg-warn/70" : "bg-bad/70",
                )}
                style={{ width: `${Math.max(bin.share > 0 ? 1.5 : 0, width)}%` }}
              />
            </div>
            <span className="w-24 shrink-0 text-[11px] tabular text-ink-soft">
              {formatShare(bin.share)} ({bin.count})
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ==========================================================================
   Headline figure
   ========================================================================== */

function AccuracyTile({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-line bg-card p-4">
      <span className="eyebrow">{label}</span>
      <p
        className={cn(
          "font-display mt-1.5 text-[30px] leading-none font-bold tabular",
          accent,
        )}
      >
        {value}
      </p>
      <p className="mt-2 text-[11.5px] leading-relaxed text-ink-soft">{sub}</p>
    </div>
  );
}

/* ==========================================================================
   Panel
   ========================================================================== */

export function AccuracyPanel({ data }: { data: BenchmarkResults }) {
  const reports = React.useMemo(() => accuracyForAll(data), [data]);
  const [modelKey, setModelKey] = React.useState<string>(data.best_model);

  if (reports.length === 0) {
    return (
      <SectionCard id="accuracy" title={ACCURACY_SECTION.title}>
        <Alert variant="warn">
          <Info />
          <AlertTitle>Per-cycle predictions are not in this benchmark run</AlertTitle>
          <AlertDescription>
            Accuracy bands are computed from the held-out predictions themselves.
            Regenerate the benchmark with{" "}
            <code className="font-mono">python -m backend.batris.benchmark</code> to
            enable this section.
          </AlertDescription>
        </Alert>
      </SectionCard>
    );
  }

  const selected =
    reports.find((report) => report.modelKey === modelKey) ?? reports[0];

  // Rank by MAE so the strongest model is easy to find in the table.
  const ranked = [...reports].sort((a, b) => a.maeSohPoints - b.maeSohPoints);
  const best = ranked[0];

  return (
    <div className="grid gap-3">
      <SectionCard
        id="accuracy"
        title={ACCURACY_SECTION.title}
        description={ACCURACY_SECTION.body}
        aside={
          <Badge variant="outline" className="gap-1.5 px-3 py-1.5 text-[12.5px]">
            <Target className="size-3.5" />
            {best.n.toLocaleString()} held-out predictions
          </Badge>
        }
      >
        {/* ------------------------------------------------ headline figures */}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <AccuracyTile
            label="Typical error"
            value={`${best.maeSohPoints.toFixed(2)} pts`}
            sub={`Mean absolute error of ${best.modelName} on batteries it never saw during training.`}
            accent="text-signal/65"
          />
          <AccuracyTile
            label="Within ±5 points"
            value={formatShare(best.within[5])}
            sub="Share of held-out predictions landing within five SOH points of the measured capacity."
            accent="text-good/65"
          />
          <AccuracyTile
            label="Agreement (R²)"
            value={best.r2.toFixed(3)}
            sub="Proportion of the real variation in capacity the estimates reproduce."
          />
          <AccuracyTile
            label="Worst case"
            value={`${best.maxAbsSohPoints.toFixed(1)} pts`}
            sub={`Largest single miss across all folds. The 90th percentile is ${best.p90AbsSohPoints.toFixed(1)} points.`}
            accent="text-warn/65"
          />
        </div>

        <Alert variant="estimated" className="mt-4">
          <Info />
          <AlertTitle>
            Read as: for a used pack, this estimate is typically within{" "}
            {best.maeSohPoints.toFixed(1)} SOH points of the bench capacity test.
        </AlertTitle>
          <AlertDescription>{ACCURACY_SECTION.note}</AlertDescription>
        </Alert>
      </SectionCard>

      {/* ------------------------------------------------- tolerance table */}
      <SectionCard
        title="Share of predictions inside a tolerance"
        description="The same held-out predictions, expressed as the proportion landing within a stated number of SOH points. A buyer deciding whether to pay for a bench test cares about this far more than about a mean."
      >
        <div className="overflow-x-auto rounded-xl border border-line">
          <Table>
            <TableHeader>
              <TableRow className="bg-mist/50">
                <TableHead>Model</TableHead>
                {ACCURACY_TOLERANCES.map((tolerance) => (
                  <TableHead key={tolerance} className="text-right whitespace-nowrap">
                    ±{tolerance} pts
                  </TableHead>
                ))}
                <TableHead className="text-right">Median error</TableHead>
                <TableHead className="text-right">MAE</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {ranked.map((report) => {
                const isBest = report.modelKey === best.modelKey;
                return (
                  <TableRow
                    key={report.modelKey}
                    className={isBest ? "bg-signal/5" : undefined}
                  >
                    <TableCell className="font-medium text-ink">
                      <span className="flex items-center gap-2 whitespace-nowrap">
                        {report.modelName}
                        {isBest ? (
                          <Badge variant="signal" className="px-1.5 py-0 text-[10.5px]">
                            Best
                          </Badge>
                        ) : null}
                      </span>
                    </TableCell>
                    {ACCURACY_TOLERANCES.map((tolerance) => (
                      <TableCell
                        key={tolerance}
                        className="text-right font-mono tabular text-ink"
                      >
                        {formatShare(report.within[tolerance])}
                      </TableCell>
                    ))}
                    <TableCell className="text-right font-mono tabular text-ink">
                      {report.medianAbsSohPoints.toFixed(2)}
                    </TableCell>
                    <TableCell
                      className={cn(
                        "text-right font-mono tabular",
                        isBest ? "font-bold text-signal" : "text-ink",
                      )}
                    >
                      {report.maeSohPoints.toFixed(2)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </SectionCard>

      {/* --------------------------------------- parity + error distribution */}
      <SectionCard
        title="Estimated against measured"
        description="Each dot is one held-out cycle. The dashed diagonal is where a perfect estimator would place every point, and the green corridor marks ±5 SOH points. Spread away from the diagonal is the error."
      >
        <div className="grid gap-3 sm:max-w-xs">
          <div className="grid gap-1.5">
            <Label htmlFor="accuracyModel" className="eyebrow">
              Model
            </Label>
            <Select value={selected.modelKey} onValueChange={setModelKey}>
              <SelectTrigger id="accuracyModel">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ranked.map((report) => (
                  <SelectItem key={report.modelKey} value={report.modelKey}>
                    {report.modelName} · {report.maeSohPoints.toFixed(2)} MAE
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-8">
          <div>
            <ParityPlot report={selected} />
          </div>

          <div className="min-w-0">
            <h3 className="eyebrow mb-3">Absolute error distribution</h3>
            <ErrorDistribution report={selected} />

            <div className="mt-5 grid gap-2 sm:grid-cols-2">
              <div className="rounded-lg border border-line bg-mist/50 px-3 py-2.5">
                <span className="eyebrow">Mean bias</span>
                <p className="mt-1 text-[15px] font-semibold tabular">
                  {selected.biasSohPoints >= 0 ? "+" : ""}
                  {selected.biasSohPoints.toFixed(2)} pts
                </p>
                <p className="mt-0.5 text-[10.5px] leading-snug text-ink-soft">
                  {Math.abs(selected.biasSohPoints) < 0.5
                    ? "Near zero: the model is not systematically optimistic or pessimistic."
                    : selected.biasSohPoints > 0
                      ? "Positive: this model reads slightly high, which flatters a used pack."
                      : "Negative: this model reads slightly low, which is the safer direction to err."}
                </p>
              </div>
              <div className="rounded-lg border border-line bg-mist/50 px-3 py-2.5">
                <span className="eyebrow">RMSE</span>
                <p className="mt-1 text-[15px] font-semibold tabular">
                  {selected.rmseSohPoints.toFixed(2)} pts
                </p>
                <p className="mt-0.5 text-[10.5px] leading-snug text-ink-soft">
                  Above the MAE of {selected.maeSohPoints.toFixed(2)}, so a minority of
                  cycles carry most of the error.
                </p>
              </div>
            </div>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
