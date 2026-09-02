"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, Filter, PackageOpen, Plus, RefreshCw } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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
import { Skeleton } from "@/components/ui/skeleton";
import { ListingCard } from "@/components/market/listing-card";
import { formatChemistry } from "@/components/market/shared";
import { browseMarket } from "@/lib/api";
import {
  CHEMISTRY_FILTER_ALL,
  GRADE_FILTER_ALL,
  MARKET,
  REUSE_GRADES,
} from "@/lib/constants";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { MarketBrowseResult } from "@/lib/types";

/* ==========================================================================
   Grade count tiles
   ========================================================================== */

// const TILE_ACCENT: Record<string, string> = {
//   A: "text-good",
//   B: "text-signal",
//   C: "text-warn",
//   RECYCLE: "text-bad",
// };
const TILE_ACCENT: Record<string, string> = {
  A: "text-good/65",
  B: "text-signal/65",
  C: "text-warn/65",
  RECYCLE: "text-bad/65",
};

// function GradeTiles({
//   counts,
//   active,
//   onSelect,
// }: {
//   counts: Record<string, number>;
//   active: string;
//   onSelect: (grade: string) => void;
// }) {
//   return (
//     <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
//       {REUSE_GRADES.map((grade) => {
//         const selected = active === grade.value;
//         return (
//           <button
//             key={grade.value}
//             type="button"
//             // The tiles double as the fastest way to filter, so a reader who
//             // sees "2 in grade C" can act on it in one click.
//             onClick={() => onSelect(selected ? GRADE_FILTER_ALL : grade.value)}
//             aria-pressed={selected}
//             className={cn(
//               "cursor-pointer rounded-xl border px-3.5 py-3 text-left transition-colors",
//               selected
//                 ? "border-ink bg-mist"
//                 : "border-line bg-card hover:border-ink/25 hover:bg-mist/50",
//             )}
//           >
//             <span className="eyebrow">
//               {grade.value === "RECYCLE" ? "Recycle" : grade.value}
//             </span>
//             <span
//               className={cn(
//                 "font-display mt-1 block text-[26px] leading-none font-bold tabular",
//                 TILE_ACCENT[grade.value] ?? "text-ink",
//               )}
//             >
//               {counts[grade.value] ?? 0}
//             </span>
//           </button>
//         );
//       })}
//     </div>
//   );
// }
function GradeTiles({
  counts,
  active,
  onSelect,
}: {
  counts: Record<string, number>;
  active: string;
  onSelect: (grade: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {REUSE_GRADES.map((grade) => {
        const selected = active === grade.value;

        return (
          <button
            key={grade.value}
            type="button"
            onClick={() =>
              onSelect(selected ? GRADE_FILTER_ALL : grade.value)
            }
            aria-pressed={selected}
            className={cn(
              "cursor-pointer rounded-xl border px-3.5 py-3 text-left transition-colors",
              // selected
              //   ? "border-ink bg-mist"
              //   : "border-line bg-card hover:border-ink/25 hover:bg-mist/50"
              selected
              ? "border-line bg-mist shadow-sm"
              : "border-line bg-card hover:border-ink/25 hover:bg-mist/50"
            )}
          >
            <span
              className={cn(
                "block text-[15px] font-semibold uppercase tracking-[0.12em]",
                TILE_ACCENT[grade.value] ?? "text-ink"
              )}
            >
              {grade.value === "RECYCLE" ? "Recycle" : grade.value}
            </span>

            <span className="font-display mt-1 block text-[16px] leading-none font-semibold tabular text-ink">
              {counts[grade.value] ?? 0}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/* ==========================================================================
   Shell
   ========================================================================== */

export function MarketShell() {
  const { user } = useAuth();

  const [grade, setGrade] = React.useState<string>(GRADE_FILTER_ALL);
  const [chemistry, setChemistry] = React.useState<string>(CHEMISTRY_FILTER_ALL);
  const [minSoh, setMinSoh] = React.useState<string>("");
  const [applied, setApplied] = React.useState<number | null>(null);

  const [data, setData] = React.useState<MarketBrowseResult | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await browseMarket({ grade, chemistry, minSoh: applied });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [grade, chemistry, applied]);

  React.useEffect(() => {
    void load();
  }, [load]);

  // The retained-SOH box is typed into, so it commits on Enter or blur rather
  // than firing a request on every keystroke.
  function commitMinSoh() {
    const parsed = minSoh.trim() === "" ? null : Number(minSoh);
    setApplied(parsed != null && Number.isFinite(parsed) ? parsed : null);
  }

  const activeFilters =
    (grade !== GRADE_FILTER_ALL ? 1 : 0) +
    (chemistry !== CHEMISTRY_FILTER_ALL ? 1 : 0) +
    (applied != null ? 1 : 0);

  function reset() {
    setGrade(GRADE_FILTER_ALL);
    setChemistry(CHEMISTRY_FILTER_ALL);
    setMinSoh("");
    setApplied(null);
  }

  return (
    <div className="mx-auto max-w-[1320px] px-5 py-10 sm:px-8 sm:py-14">
      {/* ---------------------------------------------------------- header */}
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr] lg:items-start lg:gap-10">
        <div>
          <p className="eyebrow">{MARKET.eyebrow}</p>
          <h1 className="font-display mt-3 text-[clamp(2rem,4.4vw,3.25rem)] leading-[1.03] font-bold tracking-[-0.045em]">
            {MARKET.title}
          </h1>
          <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-ink-soft">
            {MARKET.body}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button asChild>
              <Link href={user ? "/dashboard?view=own" : "/login?next=%2Fdashboard%3Fview%3Down"}>
                <Plus /> List a battery
              </Link>
            </Button>
            {user ? (
              <Button variant="outline" asChild>
                <Link href="/account#listings">My listings</Link>
              </Button>
            ) : null}
          </div>
        </div>

        {data ? (
          <div>
            <p className="eyebrow mb-2">Inventory by reuse grade</p>
            <GradeTiles counts={data.counts} active={grade} onSelect={setGrade} />
            <p className="mt-2 text-[11.5px] text-ink-soft">
              Counts cover the whole active inventory, not the current filter. Tap a
              grade to filter by it.
            </p>
          </div>
        ) : (
          <Skeleton className="h-[104px] rounded-xl" />
        )}
      </div>

      {/* --------------------------------------------------------- filters */}
      <div className="mt-8 rounded-xl border border-line bg-card p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-[14px] font-semibold">Filter inventory</h2>
            <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">
              Grades come from the same safety and second-life assessment pipeline used
              on the battery dashboard.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="gap-1.5">
              <Filter className="size-3" />
              {data ? `${data.filtered} of ${data.total}` : "\u2014"}
            </Badge>
            {activeFilters > 0 ? (
              <Button variant="ghost" size="sm" onClick={reset}>
                Clear
              </Button>
            ) : null}
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="grid gap-1.5">
            <Label htmlFor="marketGrade" className="eyebrow">
              Reuse grade
            </Label>
            <Select value={grade} onValueChange={setGrade}>
              <SelectTrigger id="marketGrade">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={GRADE_FILTER_ALL}>All grades</SelectItem>
                {REUSE_GRADES.map((entry) => (
                  <SelectItem key={entry.value} value={entry.value}>
                    {entry.label} · {entry.headline}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="marketChemistry" className="eyebrow">
              Chemistry
            </Label>
            <Select value={chemistry} onValueChange={setChemistry}>
              <SelectTrigger id="marketChemistry">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={CHEMISTRY_FILTER_ALL}>All chemistries</SelectItem>
                {(data?.chemistries ?? []).map((entry) => (
                  <SelectItem key={entry} value={entry}>
                    {formatChemistry(entry)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="marketMinSoh" className="eyebrow">
              Minimum retained SOH (%)
            </Label>
            <Input
              id="marketMinSoh"
              type="number"
              min={0}
              max={100}
              inputMode="decimal"
              placeholder="e.g. 70"
              value={minSoh}
              onChange={(event) => setMinSoh(event.target.value)}
              onBlur={commitMinSoh}
              onKeyDown={(event) => {
                if (event.key === "Enter") commitMinSoh();
              }}
            />
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------- inventory */}
      <div className="mt-6">
        {error ? (
          <Alert variant="bad">
            <AlertTriangle />
            <AlertTitle>The market could not be loaded</AlertTitle>
            <AlertDescription>
              <p className="mb-2">{error}</p>
              <p className="text-[12.5px]">
                Listings are stored in MongoDB. Check that the database is reachable and
                that <code className="font-mono">MONGODB_URI</code> is set, then reload.
              </p>
              <Button variant="outline" size="sm" className="mt-3" onClick={() => void load()}>
                <RefreshCw /> Try again
              </Button>
            </AlertDescription>
          </Alert>
        ) : loading ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2].map((index) => (
              <Skeleton key={index} className="h-[420px] rounded-xl" />
            ))}
          </div>
        ) : data && data.items.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {data.items.map((listing) => (
              <ListingCard key={listing.listing_id} listing={listing} />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-line bg-mist/40 px-6 py-14 text-center">
            <PackageOpen className="mx-auto size-6 text-ink-soft" />
            <p className="mt-3 text-[15px] font-semibold">
              {data && data.total > 0 ? MARKET.noMatchTitle : MARKET.emptyTitle}
            </p>
            <p className="mx-auto mt-2 max-w-md text-[13px] leading-relaxed text-ink-soft">
              {data && data.total > 0 ? MARKET.noMatchBody : MARKET.emptyBody}
            </p>
            {data && data.total > 0 ? (
              <Button variant="outline" className="mt-5" onClick={reset}>
                Clear filters
              </Button>
            ) : (
              <Button className="mt-5" asChild>
                <Link href="/dashboard?view=own">Assess a battery</Link>
              </Button>
            )}
          </div>
        )}
      </div>

      <p className="mt-8 border-t border-line pt-5 text-[12px] leading-relaxed text-ink-soft">
        {MARKET.contactNote}
      </p>
    </div>
  );
}
