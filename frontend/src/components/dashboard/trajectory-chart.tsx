"use client";

import * as React from "react";
import { CHART, CHART_LEGEND } from "@/lib/constants";
import type { Trajectory } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Drawn as hand-built SVG rather than through a plotting library, exactly as
 * the original dashboard was: it keeps the frontend dependency-free at the
 * point of rendering, and a capacity curve needs one thing no generic chart
 * component does well — the measured series must break at gaps rather than
 * interpolate, because a straight line there would imply measurements that
 * were never taken.
 */

const { width: W, height: H, margin: M } = CHART;
const IW = W - M.left - M.right;
const IH = H - M.top - M.bottom;

function buildSegments(
  values: (number | null)[],
  cycles: number[],
  x: (c: number) => number,
  y: (v: number) => number,
): string[] {
  const segments: string[] = [];
  let current: string[] = [];
  values.forEach((v, i) => {
    if (v === null || v === undefined || !Number.isFinite(v)) {
      if (current.length > 1) segments.push(current.join(" "));
      current = [];
    } else {
      current.push(`${x(cycles[i]).toFixed(1)},${y(v).toFixed(1)}`);
    }
  });
  if (current.length > 1) segments.push(current.join(" "));
  return segments;
}

export function TrajectoryChart({
  trajectory,
  markCycle,
}: {
  trajectory: Trajectory;
  markCycle: number;
}) {
  const [hover, setHover] = React.useState<number | null>(null);
  const svgRef = React.useRef<SVGSVGElement | null>(null);

  const cycles = trajectory.cycle_index;
  const xMin = Math.min(...cycles);
  const xMax = Math.max(...cycles);

  const measuredValues = trajectory.measured_soh.filter(
    (v): v is number => v !== null && Number.isFinite(v),
  );
  // 0.8 is always in range so the end-of-life line is never clipped off-axis.
  const all = [...trajectory.estimated_soh, ...measuredValues, 0.8];
  const yMin = Math.max(0, Math.min(...all) - CHART.yPadding);
  const yMax = Math.max(...all) + CHART.yPadding;

  const x = React.useCallback(
    (c: number) => M.left + ((c - xMin) / Math.max(1, xMax - xMin)) * IW,
    [xMin, xMax],
  );
  const y = React.useCallback(
    (v: number) => M.top + (1 - (v - yMin) / (yMax - yMin)) * IH,
    [yMin, yMax],
  );

  const measuredSegments = buildSegments(trajectory.measured_soh, cycles, x, y);
  const estimatedSegments = buildSegments(trajectory.estimated_soh, cycles, x, y);
  const anomalySet = React.useMemo(
    () => new Set(trajectory.anomalous_cycles),
    [trajectory.anomalous_cycles],
  );
  const markIndex = cycles.indexOf(markCycle);

  const handleMove = (event: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const px = ((event.clientX - rect.left) / rect.width) * W;
    if (px < M.left || px > W - M.right) {
      setHover(null);
      return;
    }
    const value = xMin + ((px - M.left) / IW) * (xMax - xMin);
    let nearest = 0;
    let best = Infinity;
    cycles.forEach((c, i) => {
      const d = Math.abs(c - value);
      if (d < best) {
        best = d;
        nearest = i;
      }
    });
    setHover(nearest);
  };

  const hoverCycle = hover !== null ? cycles[hover] : null;
  const hoverEstimated = hover !== null ? trajectory.estimated_soh[hover] : null;
  const hoverMeasured = hover !== null ? trajectory.measured_soh[hover] : null;

  return (
    <div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="block w-full select-none"
        onMouseMove={handleMove}
        onMouseLeave={() => setHover(null)}
        role="img"
        aria-label="Estimated and measured state of health against cycle number"
      >
        {/* horizontal gridlines and the y axis */}
        {Array.from({ length: CHART.yTicks + 1 }, (_, i) => {
          const v = yMin + (i / CHART.yTicks) * (yMax - yMin);
          const yy = y(v);
          return (
            <g key={`y-${i}`}>
              <line
                x1={M.left}
                y1={yy}
                x2={W - M.right}
                y2={yy}
                stroke={CHART.colors.grid}
                strokeWidth={1}
              />
              <text
                x={M.left - 10}
                y={yy + 4}
                fill={CHART.colors.axis}
                fontSize={11}
                textAnchor="end"
              >
                {(100 * v).toFixed(0)}%
              </text>
            </g>
          );
        })}

        {/* x axis */}
        {Array.from({ length: CHART.xTicks + 1 }, (_, i) => {
          const c = xMin + (i / CHART.xTicks) * (xMax - xMin);
          return (
            <text
              key={`x-${i}`}
              x={x(c)}
              y={H - 18}
              fill={CHART.colors.axis}
              fontSize={11}
              textAnchor="middle"
            >
              {Math.round(c)}
            </text>
          );
        })}
        <text
          x={M.left + IW / 2}
          y={H - 3}
          fill={CHART.colors.axis}
          fontSize={11}
          textAnchor="middle"
        >
          Cycle number
        </text>

        {/* end of first life */}
        {0.8 >= yMin && 0.8 <= yMax && (
          <>
            <line
              x1={M.left}
              y1={y(0.8)}
              x2={W - M.right}
              y2={y(0.8)}
              stroke={CHART.colors.eol}
              strokeWidth={1.2}
              strokeDasharray="6 4"
            />
            <text
              x={W - M.right}
              y={y(0.8) - 6}
              fill={CHART.colors.axis}
              fontSize={10}
              textAnchor="end"
            >
              80% end of first life
            </text>
          </>
        )}

        {/* measured series — breaks at gaps */}
        {measuredSegments.map((points, i) => (
          <polyline
            key={`m-${i}`}
            points={points}
            fill="none"
            stroke={CHART.colors.measured}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}

        {/* estimated series */}
        {estimatedSegments.map((points, i) => (
          <polyline
            key={`e-${i}`}
            points={points}
            fill="none"
            stroke={CHART.colors.estimated}
            strokeWidth={1.8}
            strokeDasharray="5 3"
            strokeLinejoin="round"
          />
        ))}

        {/* anomalous cycles */}
        {cycles.map((c, i) =>
          anomalySet.has(c) ? (
            <circle
              key={`a-${c}`}
              cx={x(c)}
              cy={y(trajectory.estimated_soh[i])}
              r={3.2}
              fill={CHART.colors.anomaly}
              opacity={0.9}
            />
          ) : null,
        )}

        {/* the cycle currently being assessed */}
        {markIndex >= 0 && (
          <>
            <line
              x1={x(markCycle)}
              y1={M.top}
              x2={x(markCycle)}
              y2={M.top + IH}
              stroke={CHART.colors.marker}
              strokeWidth={1}
              strokeDasharray="3 3"
              opacity={0.4}
            />
            <circle
              cx={x(markCycle)}
              cy={y(trajectory.estimated_soh[markIndex])}
              r={5}
              fill="none"
              stroke={CHART.colors.marker}
              strokeWidth={1.8}
            />
          </>
        )}

        {/* hover crosshair */}
        {hoverCycle !== null && hoverEstimated !== null && (
          <>
            <line
              x1={x(hoverCycle)}
              y1={M.top}
              x2={x(hoverCycle)}
              y2={M.top + IH}
              stroke={CHART.colors.axis}
              strokeWidth={1}
              opacity={0.5}
            />
            <circle
              cx={x(hoverCycle)}
              cy={y(hoverEstimated)}
              r={3.5}
              fill={CHART.colors.estimated}
            />
            {hoverMeasured !== null && Number.isFinite(hoverMeasured) && (
              <circle
                cx={x(hoverCycle)}
                cy={y(hoverMeasured)}
                r={3.5}
                fill={CHART.colors.measured}
              />
            )}
          </>
        )}
      </svg>

      <div className="mt-1 flex min-h-[20px] flex-wrap items-center gap-x-5 text-[12px] tabular text-ink-soft">
        {hoverCycle !== null ? (
          <>
            <span>
              Cycle <span className="font-semibold text-ink">{hoverCycle}</span>
            </span>
            <span style={{ color: "var(--estimated)" }}>
              Estimated {(100 * (hoverEstimated ?? 0)).toFixed(1)}%
            </span>
            {hoverMeasured !== null && Number.isFinite(hoverMeasured) ? (
              <span style={{ color: "var(--signal)" }}>
                Measured {(100 * hoverMeasured).toFixed(1)}%
              </span>
            ) : (
              <span>No reference measurement at this cycle</span>
            )}
            {anomalySet.has(hoverCycle) ? (
              <span style={{ color: "var(--warn)" }}>Flagged anomalous</span>
            ) : null}
          </>
        ) : (
          <span className="text-ink-soft/70">Hover the chart to read a cycle.</span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-[11.5px] text-ink-soft">
        {CHART_LEGEND.map((entry) => (
          <span key={entry.key} className="inline-flex items-center gap-2">
            <span
              className={cn(
                "inline-block",
                entry.key === "anomaly"
                  ? "size-2 rounded-full"
                  : "h-[3px] w-3.5 rounded-full",
              )}
              style={{
                background:
                  CHART.colors[entry.key as keyof typeof CHART.colors] as string,
              }}
            />
            {entry.label}
          </span>
        ))}
      </div>
    </div>
  );
}
