"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Mail,
  MapPin,
  Package,
  ShieldCheck,
  User,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  Note,
  SectionCard,
  SubHeading,
} from "@/components/shared/primitives";
import { HeadlineMetrics } from "@/components/dashboard/headline-metrics";
import { HealthTimeline } from "@/components/dashboard/health-timeline";
import { TrajectoryChart } from "@/components/dashboard/trajectory-chart";
import {
  GradeBadge,
  formatCapacity,
  formatChemistry,
  formatEnergy,
  formatFormFactor,
  formatListingDate,
  gradeMeta,
  riskBadgeVariant,
} from "@/components/market/shared";
import { getMarketListing } from "@/lib/api";
import { MARKET } from "@/lib/constants";
import { EM_DASH } from "@/lib/format";
import type { MarketListingDetail } from "@/lib/types";

/* ==========================================================================
   Seller contact
   --------------------------------------------------------------------------
   There is no payment rail here on purpose. The platform's claim is about
   condition, so it hands over the contact route and stops.
   ========================================================================== */

function ContactSeller({ listing }: { listing: MarketListingDetail }) {
  const subject = `BATRIS second-life enquiry: ${listing.battery_id}`;
  const body = [
    `Hello ${listing.seller.name},`,
    "",
    `I found your listing for ${listing.battery_id} on the BATRIS second-life market.`,
    `Assessed retained SOH: ${listing.soh_percent.toFixed(1)}% (reuse grade ${listing.grade}).`,
    "",
    "I would like to ask about:",
    "- availability",
    "- collection or shipping",
    "- whether a certified capacity test has been carried out",
    "",
    "Thank you.",
  ].join("\n");

  const mailto = `mailto:${encodeURIComponent(listing.seller.email)}?subject=${encodeURIComponent(
    subject,
  )}&body=${encodeURIComponent(body)}`;

  return (
    <SectionCard
      title="Contact the seller"
      description={MARKET.contactNote}
      id="contact"
    >
      <div className="rounded-xl border border-line bg-mist/50 p-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full border border-line bg-paper">
            <User className="size-4 text-ink-soft" />
          </span>
          <div className="min-w-0">
            <p className="text-[14px] font-semibold">{listing.seller.name}</p>
            <a
              href={`mailto:${listing.seller.email}`}
              className="mt-0.5 block truncate text-[12.5px] font-medium text-signal underline underline-offset-2"
            >
              {listing.seller.email}
            </a>
            {listing.location ? (
              <p className="mt-1.5 inline-flex items-center gap-1.5 text-[12px] text-ink-soft">
                <MapPin className="size-3" />
                {listing.location}
              </p>
            ) : null}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button asChild>
            <a href={mailto}>
              <Mail /> Email the seller
            </a>
          </Button>
        </div>
      </div>

      <div className="mt-3">
        <Note>
          This seller published their name and email with the listing so buyers can
          reach them. Agree terms, payment and collection between yourselves; BATRIS is
          not a party to the transaction and holds no funds.
        </Note>
      </div>
    </SectionCard>
  );
}

/* ==========================================================================
   Detail
   ========================================================================== */

export function ListingDetail({ listingId }: { listingId: string }) {
  const [listing, setListing] = React.useState<MarketListingDetail | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getMarketListing(listingId)
      .then((result) => {
        if (!cancelled) setListing(result);
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
  }, [listingId]);

  if (loading) {
    return (
      <div className="mx-auto max-w-[1320px] px-5 py-10 sm:px-8">
        <Skeleton className="mb-4 h-10 w-72 rounded-lg" />
        <div className="grid gap-3">
          <Skeleton className="h-40 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error || !listing) {
    return (
      <div className="mx-auto max-w-[1320px] px-5 py-10 sm:px-8">
        <Alert variant="bad">
          <AlertTriangle />
          <AlertTitle>This listing could not be opened</AlertTitle>
          <AlertDescription>
            <p className="mb-3">{error ?? "No listing data received."}</p>
            <Button variant="outline" size="sm" asChild>
              <Link href="/market">
                <ArrowLeft /> Back to the market
              </Link>
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const assessment = listing.assessment;
  const meta = gradeMeta(listing.grade);

  return (
    <div className="mx-auto max-w-[1320px] px-5 py-8 sm:px-8 sm:py-12">
      <Link
        href="/market"
        className="inline-flex items-center gap-1.5 text-[12.5px] font-medium text-ink-soft transition-colors hover:text-ink"
      >
        <ArrowLeft className="size-3.5" /> Back to the second-life market
      </Link>

      {/* ---------------------------------------------------------- header */}
      <div className="mt-5 flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div className="min-w-0">
          <p className="eyebrow">Second-life listing</p>
          <h1 className="font-display mt-2 text-[clamp(2rem,4vw,3rem)] leading-[1.04] font-bold tracking-[-0.045em]">
            {listing.battery_id}
          </h1>
          {listing.title ? (
            <p className="mt-2 max-w-2xl text-[14.5px] leading-relaxed">{listing.title}</p>
          ) : null}
          <p className="mt-2 text-[12.5px] text-ink-soft">
            {formatChemistry(listing.chemistry)}
            {listing.form_factor ? ` \u00b7 ${formatFormFactor(listing.form_factor)}` : ""}
            {listing.format_display_name ? ` \u00b7 ${listing.format_display_name}` : ""}
            {" \u00b7 listed "}
            {formatListingDate(listing.created_at)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <GradeBadge grade={listing.grade} className="px-3 py-1 text-[12px]" />
          <Badge variant={riskBadgeVariant(listing.risk_band)} className="px-3 py-1 text-[12px]">
            <ShieldCheck className="size-3" />
            Risk {listing.risk_band ?? EM_DASH}
          </Badge>
          {listing.passport_id ? (
            <Badge variant="estimated" className="px-3 py-1 text-[12px]">
              <BadgeCheck className="size-3" />
              Signed passport attached
            </Badge>
          ) : null}
          {listing.is_reference_fleet ? (
            <Badge variant="outline" className="px-3 py-1 text-[12px]">
              <Package className="size-3" />
              Reference fleet
            </Badge>
          ) : null}
        </div>
      </div>

      <div className="mt-8 grid gap-3">
        {/* -------------------------------------------------- at a glance */}
        <SectionCard
          title="What is on offer"
          description={
            meta
              ? `${meta.headline}. ${listing.grade_recommendation ?? meta.summary}`
              : undefined
          }
        >
          <KeyValueGrid>
            <KeyValue
              label="Retained SOH"
              tag="estimated"
              value={`${listing.soh_percent.toFixed(1)}%`}
            />
            <KeyValue
              label="Retained capacity"
              value={formatCapacity(listing.retained_capacity_ah)}
            />
            <KeyValue
              label="Remaining energy"
              value={formatEnergy(listing.remaining_energy_wh)}
            />
            <KeyValue
              label="Grade confidence"
              value={listing.grade_confidence ?? EM_DASH}
            />
            <KeyValue
              label="Cycles observed"
              value={listing.cycles_observed ?? EM_DASH}
            />
            <KeyValue
              label="Anomaly status"
              value={
                listing.anomaly_count === 0
                  ? "Clear"
                  : `${listing.anomaly_count} active`
              }
            />
          </KeyValueGrid>

          {listing.notes ? (
            <div className="mt-4 rounded-xl border border-line bg-mist/50 p-4">
              <p className="eyebrow">Seller&apos;s notes</p>
              <p className="mt-1.5 text-[13px] leading-relaxed">{listing.notes}</p>
            </div>
          ) : null}

          {listing.grade_is_ambiguous ? (
            <Alert variant="warn" className="mt-4">
              <AlertTriangle />
              <AlertTitle>
                The confidence interval spans grades {listing.worst_case_grade}
                {"\u2013"}
                {listing.best_case_grade}
              </AlertTitle>
              <AlertDescription>
                {listing.next_step ??
                  "This estimate is not precise enough to support a binding resale decision. Commission a certified capacity test before committing."}
              </AlertDescription>
            </Alert>
          ) : null}

          {listing.safety_override_applied ? (
            <Alert variant="bad" className="mt-3">
              <AlertTriangle />
              <AlertTitle>Grade set by safety, not by capacity</AlertTitle>
              <AlertDescription>
                The safety assessment placed this pack in the HIGH risk band, so reuse is
                not recommended regardless of how much capacity remains.
              </AlertDescription>
            </Alert>
          ) : null}
        </SectionCard>

        {/* ---------------------------------------------------- contact */}
        <ContactSeller listing={listing} />

        {/* -------------------------------------------- full assessment */}
        {assessment ? (
          <>
            <HeadlineMetrics
              health={assessment.health}
              safety={assessment.safety}
              anomaly={assessment.anomaly}
              secondLife={assessment.second_life}
              eolThreshold={assessment.health.eol_threshold}
              anomalySub={`${assessment.anomaly.recent_anomalous_cycles ?? 0} of last ${
                assessment.anomaly.recent_window_cycles ?? 0
              } cycles flagged`}
            />

            <HealthTimeline assessment={assessment} id="timeline" />

            {assessment.trajectory ? (
              <SectionCard
                title="Degradation trajectory"
                description={`${assessment.battery_id} · ${assessment.total_cycles_observed} cycles observed · assessed at cycle ${assessment.cycle_index}`}
              >
                <TrajectoryChart
                  trajectory={assessment.trajectory}
                  markCycle={assessment.cycle_index}
                />
              </SectionCard>
            ) : null}

            <SectionCard
              title="Why this battery is degrading"
              description={assessment.degradation_summary}
            >
              <DegradationFactors factors={assessment.degradation_factors} />
              <Caveat>{assessment.explanation_caveat}</Caveat>
            </SectionCard>

            <div className="grid gap-3 lg:grid-cols-2">
              <SectionCard title="Safety assessment">
                <SubHeading>Risk drivers</SubHeading>
                <RiskDrivers drivers={assessment.safety.risk_drivers} />
                <SubHeading>Safe charging envelope</SubHeading>
                <ChargingEnvelopeGrid
                  envelope={assessment.safety.safe_charging_envelope}
                />
              </SectionCard>
              <SectionCard title="Recommended practice">
                <Recommendations items={assessment.safety.recommendations} />
              </SectionCard>
            </div>

            <SectionCard title="Anomaly detections">
              <AnomalyList anomaly={assessment.anomaly} />
            </SectionCard>

            <SectionCard
              title="Where these numbers came from"
              description="The listing cannot be edited by hand: every figure above is copied from this assessment."
            >
              <KeyValueGrid>
                <KeyValue
                  small
                  label="Model variant"
                  value={assessment.model_provenance.soh_model_variant}
                />
                <KeyValue
                  small
                  label="Validation method"
                  value={assessment.model_provenance.validation_method}
                />
                <KeyValue
                  small
                  label="Out-of-sample MAE"
                  value={
                    assessment.model_provenance.validation_mae_soh_points != null
                      ? `${assessment.model_provenance.validation_mae_soh_points} SOH pts`
                      : EM_DASH
                  }
                />
                <KeyValue
                  small
                  label="Assessed at"
                  value={formatListingDate(listing.assessed_at)}
                />
              </KeyValueGrid>
            </SectionCard>
          </>
        ) : (
          <SectionCard title="Full assessment">
            <Note>
              The assessment behind this listing is not available. Only the summary
              figures above can be shown.
            </Note>
          </SectionCard>
        )}
      </div>
    </div>
  );
}
