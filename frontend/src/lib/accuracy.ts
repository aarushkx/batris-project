/**
 * Prediction accuracy, derived from the benchmark's leave-one-battery-out
 * predictions.
 *
 * "What is your accuracy?" has no single number as an answer for a regression
 * model, and quoting only MAE is a poor response: 2.06 SOH points means little
 * to a reader who does not already know what a plausible error looks like.
 * These helpers reduce the same held-out predictions to three complementary
 * views — typical error, agreement with ground truth, and the share of
 * predictions landing inside a stated tolerance — which together answer the
 * question honestly.
 *
 * Everything is computed from `trajectories` in the benchmark report, so each
 * point comes from a model that never saw that battery during training. There
 * is no in-sample figure anywhere in here.
 */

import { ACCURACY_TOLERANCES } from "@/lib/constants";
import type { BenchmarkModelResult, BenchmarkResults } from "@/lib/types";

export interface ParityPoint {
  /** Measured SOH, in percentage points. */
  measured: number;
  /** Estimated SOH, in percentage points. */
  estimated: number;
  battery: string;
}

export interface AccuracyReport {
  modelKey: string;
  modelName: string;
  /** Number of held-out cycle predictions behind these figures. */
  n: number;
  maeSohPoints: number;
  rmseSohPoints: number;
  medianAbsSohPoints: number;
  /** 90th percentile of absolute error: the "bad day" figure. */
  p90AbsSohPoints: number;
  maxAbsSohPoints: number;
  biasSohPoints: number;
  r2: number;
  /** Share of predictions within ±k SOH points, keyed by k. */
  within: Record<number, number>;
  points: ParityPoint[];
  absErrors: number[];
}

function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return Number.NaN;
  const position = (sorted.length - 1) * q;
  const low = Math.floor(position);
  const high = Math.ceil(position);
  if (low === high) return sorted[low];
  return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

/**
 * Flatten every fold of one model into a single set of held-out predictions.
 * Returns null when the report predates trajectory capture.
 */
export function accuracyForModel(
  model: BenchmarkModelResult,
): AccuracyReport | null {
  const folds = model.trajectories;
  if (!folds) return null;

  const points: ParityPoint[] = [];
  for (const [battery, fold] of Object.entries(folds)) {
    const length = Math.min(fold.measured_soh.length, fold.estimated_soh.length);
    for (let index = 0; index < length; index += 1) {
      const measured = fold.measured_soh[index];
      const estimated = fold.estimated_soh[index];
      if (!Number.isFinite(measured) || !Number.isFinite(estimated)) continue;
      points.push({
        measured: 100 * measured,
        estimated: 100 * estimated,
        battery,
      });
    }
  }

  if (points.length === 0) return null;

  const errors = points.map((point) => point.estimated - point.measured);
  const absErrors = errors.map(Math.abs);
  const n = points.length;

  const mae = absErrors.reduce((sum, value) => sum + value, 0) / n;
  const rmse = Math.sqrt(
    errors.reduce((sum, value) => sum + value * value, 0) / n,
  );
  const bias = errors.reduce((sum, value) => sum + value, 0) / n;

  // R² against the measured mean, on the same percentage-point scale.
  const measuredMean =
    points.reduce((sum, point) => sum + point.measured, 0) / n;
  const ssRes = errors.reduce((sum, value) => sum + value * value, 0);
  const ssTot = points.reduce(
    (sum, point) => sum + (point.measured - measuredMean) ** 2,
    0,
  );
  const r2 = ssTot > 0 ? 1 - ssRes / ssTot : Number.NaN;

  const sortedAbs = [...absErrors].sort((a, b) => a - b);

  const within: Record<number, number> = {};
  for (const tolerance of ACCURACY_TOLERANCES) {
    within[tolerance] =
      absErrors.filter((value) => value <= tolerance).length / n;
  }

  return {
    modelKey: model.model_key,
    modelName: model.model_display_name,
    n,
    maeSohPoints: mae,
    rmseSohPoints: rmse,
    medianAbsSohPoints: quantile(sortedAbs, 0.5),
    p90AbsSohPoints: quantile(sortedAbs, 0.9),
    maxAbsSohPoints: sortedAbs[sortedAbs.length - 1],
    biasSohPoints: bias,
    r2,
    within,
    points,
    absErrors,
  };
}

/** Accuracy for every model that has captured trajectories. */
export function accuracyForAll(data: BenchmarkResults): AccuracyReport[] {
  return data.models
    .map(accuracyForModel)
    .filter((report): report is AccuracyReport => report !== null);
}

export interface HistogramBin {
  from: number;
  to: number;
  count: number;
  share: number;
}

/** Bin absolute errors so the shape of the error distribution is visible. */
export function errorHistogram(
  absErrors: number[],
  binWidth = 1,
  maxBins = 10,
): HistogramBin[] {
  if (absErrors.length === 0) return [];
  const largest = Math.max(...absErrors);
  const binCount = Math.min(maxBins, Math.max(1, Math.ceil(largest / binWidth)));
  const bins: HistogramBin[] = Array.from({ length: binCount }, (_, index) => ({
    from: index * binWidth,
    to: (index + 1) * binWidth,
    count: 0,
    share: 0,
  }));

  for (const value of absErrors) {
    // Everything beyond the last bin lands in it, so the final bar reads as
    // "this much or worse" rather than silently dropping outliers.
    const index = Math.min(binCount - 1, Math.floor(value / binWidth));
    bins[index].count += 1;
  }
  for (const bin of bins) {
    bin.share = bin.count / absErrors.length;
  }
  return bins;
}

export function formatShare(share: number): string {
  if (!Number.isFinite(share)) return "\u2014";
  return `${(100 * share).toFixed(share >= 0.995 ? 0 : 1)}%`;
}
