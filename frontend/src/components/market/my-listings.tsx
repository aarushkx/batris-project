"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight, Eye, RefreshCw, Store, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/shared/primitives";
import { GradeBadge, formatListingDate } from "@/components/market/shared";
import { getMyListings, withdrawListing } from "@/lib/api";
import type { MarketListing } from "@/lib/types";

export function MyListings({ id }: { id?: string }) {
  const [listings, setListings] = React.useState<MarketListing[] | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      const result = await getMyListings();
      setListings(result.items);
    } catch (error) {
      // The market needs MongoDB; a missing database should not break the
      // whole account page, so this degrades to an empty panel with a toast.
      setListings([]);
      toast.error("Could not load your market listings", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function handleWithdraw(listing: MarketListing) {
    setBusy(listing.listing_id);
    try {
      await withdrawListing(listing.listing_id);
      toast.success("Listing withdrawn", {
        description: `${listing.battery_id} is no longer visible on the market.`,
      });
      await load();
    } catch (error) {
      toast.error("Could not withdraw the listing", {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(null);
    }
  }

  const active = (listings ?? []).filter((item) => item.status === "active");
  const withdrawn = (listings ?? []).filter((item) => item.status !== "active");

  return (
    <SectionCard
      id={id}
      title="My market listings"
      description="Batteries you have published to the second-life market. Withdrawing removes the listing and your contact details from public view."
      aside={
        <Button variant="outline" size="sm" asChild>
          <Link href="/market">
            <Store /> Market
          </Link>
        </Button>
      }
    >
      {listings === null ? (
        <p className="text-[12.5px] text-ink-soft">Loading your listings…</p>
      ) : active.length === 0 && withdrawn.length === 0 ? (
        <div className="grid gap-3">
          <p className="text-[12.5px] leading-relaxed text-ink-soft">
            Nothing listed yet. Assess a battery, then publish it from the
            &ldquo;Offer this battery for reuse&rdquo; panel underneath the assessment.
          </p>
          <div>
            <Button size="sm" asChild>
              <Link href="/dashboard?view=own">
                Assess a battery <ArrowUpRight />
              </Link>
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid gap-2">
          {[...active, ...withdrawn].map((listing) => {
            const isActive = listing.status === "active";
            return (
              <div
                key={listing.listing_id}
                className={`rounded-xl border border-line p-3.5 ${
                  isActive ? "bg-mist/40" : "bg-mist/20 opacity-70"
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[13.5px] font-semibold">{listing.battery_id}</p>
                    <p className="mt-1 text-[11.5px] text-ink-soft">
                      {listing.soh_percent.toFixed(1)}% retained SOH · risk{" "}
                      {listing.risk_band} · listed{" "}
                      {formatListingDate(listing.created_at)}
                    </p>
                    {listing.location ? (
                      <p className="mt-0.5 text-[11px] text-ink-soft/80">
                        {listing.location}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <GradeBadge grade={listing.grade} />
                    {!isActive ? (
                      <Badge variant="default" className="px-2 py-0 text-[9.5px]">
                        Withdrawn
                      </Badge>
                    ) : null}
                  </div>
                </div>

                {isActive ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" asChild>
                      <Link href={`/market/${listing.listing_id}`}>
                        <Eye /> View
                      </Link>
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-red-200/80 bg-red-100/50 text-red-700 hover:border-red-300 hover:bg-red-50 hover:text-red-800"
                      onClick={() => void handleWithdraw(listing)}
                      disabled={busy === listing.listing_id}
                    >
                      {busy === listing.listing_id ? (
                        <RefreshCw className="animate-spin" />
                      ) : (
                        <Trash2 />
                      )}
                      {busy === listing.listing_id ? "Withdrawing…" : "Withdraw"}
                    </Button>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </SectionCard>
  );
}
