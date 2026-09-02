"use client";

import Link from "next/link";
import { ArrowRight, BatteryCharging, MapPin, ShieldCheck, Store, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  GradeBadge,
  ListingStat,
  formatCapacity,
  formatChemistry,
  formatEnergy,
  formatFormFactor,
  gradeMeta,
} from "@/components/market/shared";
import { EM_DASH } from "@/lib/format";
import type { MarketListing } from "@/lib/types";

export function ListingCard({ listing }: { listing: MarketListing }) {
  const meta = gradeMeta(listing.grade);
  const recycle = listing.grade === "RECYCLE";

  return (
    <article className="flex flex-col rounded-xl border border-line bg-card p-4 transition-colors hover:border-ink/20 sm:p-5">
      {/* ------------------------------------------------------- header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="eyebrow flex items-center gap-1.5">
            <Store className="size-3" />
            <span>Inventory</span>
          </div>
          <h3 className="font-display mt-1.5 text-[22px] leading-tight font-bold tracking-[-0.03em]">
            {listing.battery_id}
          </h3>
          <p className="mt-1 text-[12px] text-ink-soft">
            {formatChemistry(listing.chemistry)}
            {listing.form_factor ? ` \u00b7 ${formatFormFactor(listing.form_factor)}` : ""}
          </p>
        </div>
        <GradeBadge grade={listing.grade} className="shrink-0" />
      </div>

      {listing.title ? (
        <p className="mt-3 text-[13px] leading-snug font-medium">{listing.title}</p>
      ) : null}

      {/* -------------------------------------------------------- stats */}
      <div className="mt-3.5 grid grid-cols-2 gap-2">
        <ListingStat
          label="Retained SOH"
          value={`${listing.soh_percent.toFixed(1)}%`}
          sub={
            listing.soh_lower_percent != null && listing.soh_upper_percent != null
              ? `90% CI ${listing.soh_lower_percent.toFixed(1)}\u2013${listing.soh_upper_percent.toFixed(1)}%`
              : undefined
          }
        />
        <ListingStat
          label="Capacity"
          value={formatCapacity(listing.retained_capacity_ah)}
          sub={
            listing.rated_capacity_ah != null
              ? `of ${formatCapacity(listing.rated_capacity_ah)} rated`
              : undefined
          }
          icon={<BatteryCharging className="size-3" />}
        />
        <ListingStat
          label="Energy"
          value={formatEnergy(listing.remaining_energy_wh)}
          icon={<Zap className="size-3" />}
        />
        <ListingStat
          label="Risk"
          value={
            <span className="inline-flex items-center gap-1.5">
              <span className="text-[15px]">{listing.risk_band ?? EM_DASH}</span>
              {listing.risk_score != null ? (
                <span className="text-[11px] font-normal text-ink-soft">
                  ({listing.risk_score.toFixed(0)})
                </span>
              ) : null}
            </span>
          }
          icon={<ShieldCheck className="size-3" />}
        />
      </div>

      {/* ------------------------------------------------- what it's for */}
      {meta ? (
        <div
          className={`mt-3 rounded-lg border px-3 py-2.5 ${
            recycle ? "border-bad/25 bg-bad/5" : "border-signal/20 bg-signal/5"
          }`}
        >
          <p className="text-[12.5px] font-semibold">{meta.headline}</p>
          <p className="mt-0.5 text-[11.5px] leading-relaxed text-ink-soft">
            {listing.grade_recommendation ?? meta.summary}
          </p>
        </div>
      ) : null}

      {/* -------------------------------------------------------- footer */}
      <div className="mt-auto pt-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px] text-ink-soft">
          {listing.cycles_observed != null ? (
            <span className="tabular">
              {listing.assessed_at_cycle != null
                ? `Cycle ${listing.assessed_at_cycle} of `
                : ""}
              {listing.cycles_observed} observed
            </span>
          ) : null}
          {listing.location ? (
            <span className="inline-flex items-center gap-1">
              <MapPin className="size-3" />
              {listing.location}
            </span>
          ) : null}
          {listing.is_reference_fleet ? (
            <Badge variant="outline" className="px-1.5 py-0 text-[9.5px]">
              Reference fleet
            </Badge>
          ) : null}
        </div>

        {/* An ambiguous grade is the single most important thing a buyer can
            know, so it is stated on the card rather than hidden in detail. */}
        {listing.grade_is_ambiguous ? (
          <p className="mt-2.5 text-[11px] leading-relaxed text-warn">
            Confidence interval spans grades {listing.worst_case_grade}
            {"\u2013"}
            {listing.best_case_grade}; additional testing is advised before committing.
          </p>
        ) : null}

        <div className="mt-3 flex items-center justify-between gap-3 border-t border-line pt-3">
          <span className="truncate text-[11.5px] text-ink-soft">
            {listing.seller.name}
          </span>
          <Link
            href={`/market/${listing.listing_id}`}
            className="inline-flex shrink-0 items-center gap-1.5 text-[12.5px] font-semibold text-ink transition-colors hover:text-signal"
          >
            Open assessment
            <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </div>
    </article>
  );
}
