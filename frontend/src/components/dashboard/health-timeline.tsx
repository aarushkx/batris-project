"use client";

import * as React from "react";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  CircleDot,
  Download,
  Flame,
  Gauge,
  Info,
  RefreshCw,
  Telescope,
  TrendingDown,
  TriangleAlert,
} from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { KeyValue, KeyValueGrid, Note, SectionCard } from "@/components/shared/primitives";
import { buildTimeline, downloadTimelinePdf } from "@/lib/api";
import { TIMELINE, TIMELINE_FILTERS, TIMELINE_PHASE } from "@/lib/constants";
import { EM_DASH } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  Assessment,
  Timeline,
  TimelineEvent,
  TimelinePhase,
  TimelineSeverity,
  UnseenAssessment,
} from "@/lib/types";

/* ==========================================================================
   Severity presentation
   --------------------------------------------------------------------------
   The same four levels the backend emits. Colour carries meaning here, so a
   reader scanning the rail can tell a threshold crossing from a detection
   without reading a word of it.
   ========================================================================== */

const SEVERITY: Record<
  TimelineSeverity,
  { label: string; dot: string; ring: string; text: string; badge: React.ComponentProps<typeof Badge>["variant"] }
> = {
  critical: {
    label: "Critical",
    dot: "bg-bad",
    ring: "ring-bad/25",
    text: "text-bad",
    badge: "bad",
  },
  warning: {
    label: "Warning",
    dot: "bg-warn",
    ring: "ring-warn/25",
    text: "text-warn",
    badge: "warn",
  },
  good: {
    label: "Clear",
    dot: "bg-good",
    ring: "ring-good/25",
    text: "text-good",
    badge: "good",
  },
  info: {
    label: "Info",
    dot: "bg-ink-soft",
    ring: "ring-line",
    text: "text-ink-soft",
    badge: "default",
  },
};

const KIND_ICON: Record<string, React.ElementType> = {
  observation_start: CalendarClock,
  state_change: TrendingDown,
  milestone: CircleDot,
  fade_acceleration: TrendingDown,
  anomaly_first: TriangleAlert,
  anomaly_cluster: TriangleAlert,
  anomaly_finding: AlertTriangle,
  thermal_excursion: Flame,
  thermal_clear: CheckCircle2,
  degradation_attribution: Info,
  assessment: Gauge,
  projection: Telescope,
  unobserved_history: Info,
};

function formatDate(value: string | null): string {
  if (!value) return EM_DASH;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/* ==========================================================================
   Phase rail — the life of the battery as proportional coloured spans
   ========================================================================== */

function PhaseRail({ phases }: { phases: TimelinePhase[] }) {
  const spans = phases.filter(
    (phase) => phase.from_cycle !== null && phase.to_cycle !== null,
  );
  if (spans.length === 0) return null;

  const start = spans[0].from_cycle ?? 0;
  const end = spans[spans.length - 1].to_cycle ?? start + 1;
  const total = Math.max(1, end - start);

  return (
    <div className="mt-1">
      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-mist">
        {spans.map((phase) => {
          const width =
            (((phase.to_cycle ?? 0) - (phase.from_cycle ?? 0) + 1) / total) * 100;
          return (
            <div
              key={`${phase.state}-${phase.from_cycle}`}
              title={`${phase.label} · cycles ${phase.from_cycle}\u2013${phase.to_cycle}`}
              style={{
                width: `${Math.max(1.5, width)}%`,
                background: TIMELINE_PHASE[phase.phase]?.colour ?? "var(--ink-soft)",
                opacity: phase.is_current ? 1 : 0.55,
              }}
            />
          );
        })}
      </div>

      <div className="mt-2 flex justify-between text-[10px] tabular text-ink-soft/70">
        <span>Cycle {start}</span>
        <span>Cycle {end}</span>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {spans.map((phase) => (
          <div
            key={`legend-${phase.state}-${phase.from_cycle}`}
            className="rounded-lg border border-line bg-mist/50 px-3 py-2.5"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="inline-flex items-center gap-2 text-[12.5px] font-semibold">
                <span
                  className="inline-block size-2 rounded-full"
                  style={{
                    background: TIMELINE_PHASE[phase.phase]?.colour ?? "var(--ink-soft)",
                  }}
                />
                {phase.label}
              </span>
              {phase.is_current ? (
                <Badge variant="outline" className="px-1.5 py-0 text-[9.5px]">
                  Current
                </Badge>
              ) : null}
            </div>
            <p className="mt-1.5 text-[11px] tabular text-ink-soft">
              Cycles {phase.from_cycle}
              {"\u2013"}
              {phase.to_cycle} · entered at {phase.entered_at_soh_percent?.toFixed(1)}% ·
              grade {phase.reuse_grade}
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-soft/85">
              {phase.meaning}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ==========================================================================
   Event row
   ========================================================================== */

function EventRow({ event, last }: { event: TimelineEvent; last: boolean }) {
  const severity = SEVERITY[event.severity] ?? SEVERITY.info;
  const Icon = KIND_ICON[event.kind] ?? CircleDot;
  const forward = event.cycle === null;

  return (
    <li className="relative grid grid-cols-[auto_1fr] gap-x-3.5 sm:gap-x-4">
      {/* spine + node */}
      <div className="relative flex w-8 shrink-0 flex-col items-center sm:w-9">
        <span
          className={cn(
            "z-10 mt-0.5 flex size-7 items-center justify-center rounded-full ring-4 sm:size-8",
            severity.dot,
            severity.ring,
          )}
        >
          <Icon className="size-3.5 text-white sm:size-4" />
        </span>
        {!last ? (
          <span
            className={cn(
              "absolute top-8 bottom-0 w-px sm:top-9",
              forward ? "border-l border-dashed border-line" : "bg-line",
            )}
          />
        ) : null}
      </div>

      {/* body */}
      <div className={cn("min-w-0", last ? "pb-1" : "pb-6")}>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Badge variant={severity.badge} className="px-2 py-0 text-[9.5px] uppercase">
            {severity.label}
          </Badge>
          <span className="text-[11.5px] tabular text-ink-soft">
            {forward ? "Projected" : `Cycle ${event.cycle}`}
          </span>
          {event.date ? (
            <span className="text-[11.5px] tabular text-ink-soft/75">
              · {formatDate(event.date)}
            </span>
          ) : null}
          {event.soh_percent != null ? (
            <span className="text-[11.5px] tabular font-medium text-estimated">
              · {event.soh_percent.toFixed(1)}% SOH
            </span>
          ) : null}
        </div>

        <p className="mt-1.5 text-[13.5px] leading-snug font-semibold tracking-[-0.01em]">
          {event.title}
        </p>
        <p className="mt-1 text-[12.5px] leading-relaxed text-ink-soft">{event.detail}</p>
      </div>
    </li>
  );
}

/* ==========================================================================
   Timeline body — rendered from a timeline document
   ========================================================================== */

export function TimelineBody({
  timeline,
  onDownload,
  downloading,
}: {
  timeline: Timeline;
  onDownload?: () => void;
  downloading?: boolean;
}) {
  const [filter, setFilter] = React.useState<string>("all");

  const events = React.useMemo(() => {
    if (filter === "attention") {
      return timeline.events.filter(
        (event) => event.severity === "warning" || event.severity === "critical",
      );
    }
    if (filter === "state_change") {
      return timeline.events.filter((event) =>
        ["state_change", "observation_start", "milestone", "assessment"].includes(
          event.kind,
        ),
      );
    }
    return timeline.events;
  }, [filter, timeline.events]);

  const { summary } = timeline;
  const snapshot = summary.source === "snapshot";

  return (
    <div className="grid gap-5">
      {/* ------------------------------------------------------- headline */}
      <div className="rounded-xl border border-line bg-mist/40 p-4 sm:p-5">
        <p className="text-[13.5px] leading-relaxed">{summary.headline}</p>

        <div className="mt-4">
          <KeyValueGrid min={150}>
            <KeyValue
              label="Condition now"
              value={summary.current_state_label}
              tag={summary.reuse_grade ? `grade ${summary.reuse_grade}` : undefined}
            />
            <KeyValue
              label="Health now"
              value={
                summary.soh_now_percent != null
                  ? `${summary.soh_now_percent.toFixed(1)}%`
                  : EM_DASH
              }
            />
            <KeyValue
              label="SOH points lost"
              value={
                summary.soh_points_lost != null
                  ? summary.soh_points_lost.toFixed(1)
                  : EM_DASH
              }
            />
            <KeyValue
              label="Condition changes"
              value={summary.n_state_changes}
            />
            <KeyValue
              label="Cycles observed"
              value={summary.cycles_observed ?? EM_DASH}
            />
            <KeyValue
              label="Flagged cycles"
              value={summary.n_anomalous_cycles}
            />
          </KeyValueGrid>
        </div>
      </div>

      {/* ---------------------------------------------------------- rail */}
      {timeline.states.length > 0 && !snapshot ? (
        <div>
          <h3 className="eyebrow mb-2">Health phases</h3>
          <PhaseRail phases={timeline.states} />
        </div>
      ) : null}

      {snapshot ? (
        <Alert variant="info">
          <Info />
          <AlertTitle>No dated history for this battery</AlertTitle>
          <AlertDescription>
            This assessment came from a single charge observation, so the platform
            cannot place transitions in time. Supplying a per-cycle log would let it
            reconstruct when each threshold was crossed.
          </AlertDescription>
        </Alert>
      ) : null}

      {/* -------------------------------------------------------- events */}
      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="eyebrow">Event log</h3>
          <div className="flex flex-wrap gap-1.5">
            {TIMELINE_FILTERS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setFilter(option.value)}
                className={cn(
                  "cursor-pointer rounded-full border px-3 py-1 text-[11.5px] font-medium transition-colors",
                  filter === option.value
                    ? "border-ink bg-ink text-white"
                    : "border-line bg-paper text-ink-soft hover:bg-mist hover:text-ink",
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {events.length === 0 ? (
          <p className="mt-4 text-[12.5px] text-ink-soft">
            Nothing recorded under this filter. That is a result, not a gap: no event
            in this battery&apos;s history met the criteria.
          </p>
        ) : (
          <ol className="mt-4">
            {events.map((event, index) => (
              <EventRow
                key={event.id}
                event={event}
                last={index === events.length - 1}
              />
            ))}
          </ol>
        )}
      </div>

      {/* ---------------------------------------------------- projection */}
      {summary.projection ? (
        <Alert variant="estimated">
          <Telescope />
          <AlertTitle>
            About {summary.projection.cycles_remaining} cycles to{" "}
            {summary.projection.target_label} (
            {summary.projection.target_soh_percent}%)
          </AlertTitle>
          <AlertDescription>
            Straight-line extrapolation of the recent fade rate of{" "}
            {summary.projection.fade_points_per_100_cycles} SOH points per 100 cycles.
            Fade usually accelerates near end of life, so treat this as an upper bound
            on remaining service rather than a prediction.
          </AlertDescription>
        </Alert>
      ) : null}

      {/* --------------------------------------------------------- footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-dashed border-line pt-4">
        <Note>{timeline.method_note}</Note>
        {onDownload ? (
          <Button variant="outline" onClick={onDownload} disabled={downloading}>
            {downloading ? <RefreshCw className="animate-spin" /> : <Download />}
            {downloading ? "Preparing PDF\u2026" : "Download timeline PDF"}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

/* ==========================================================================
   Self-contained panel — builds the timeline from an assessment
   ========================================================================== */

export function HealthTimeline({
  assessment,
  id,
  title = TIMELINE.title,
  description = TIMELINE.description,
}: {
  assessment: Assessment | UnseenAssessment | null;
  id?: string;
  title?: string;
  description?: string;
}) {
  const [timeline, setTimeline] = React.useState<Timeline | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [downloading, setDownloading] = React.useState(false);

  React.useEffect(() => {
    if (!assessment) {
      setTimeline(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    buildTimeline(assessment)
      .then((result) => {
        if (!cancelled) setTimeline(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assessment]);

  async function handleDownload() {
    if (!timeline) return;
    setDownloading(true);
    try {
      await downloadTimelinePdf(
        timeline,
        `battery_health_timeline_${timeline.battery_id}.pdf`,
      );
      toast.success("Timeline PDF downloaded");
    } catch (err) {
      toast.error("Could not prepare the timeline PDF", {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setDownloading(false);
    }
  }

  return (
    <SectionCard id={id} title={title} description={description}>
      {loading ? (
        <div className="grid gap-3">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      ) : error ? (
        <Alert variant="bad">
          <AlertTriangle />
          <AlertTitle>Could not build the timeline</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : timeline ? (
        <TimelineBody
          timeline={timeline}
          onDownload={handleDownload}
          downloading={downloading}
        />
      ) : (
        <Note>{TIMELINE.emptyNote}</Note>
      )}
    </SectionCard>
  );
}
