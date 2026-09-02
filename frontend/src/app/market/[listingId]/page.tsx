import { Suspense } from "react";
import type { Metadata } from "next";
import { ListingDetail } from "@/components/market/listing-detail";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Second-life listing" };

/**
 * Listings get their own URL rather than a modal so a seller can send a buyer
 * a link straight to the assessment behind the battery.
 */
export default async function ListingPage({
  params,
}: {
  params: Promise<{ listingId: string }>;
}) {
  const { listingId } = await params;
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-[1320px] px-5 py-10 sm:px-8">
          <Skeleton className="h-72 rounded-xl" />
        </div>
      }
    >
      <ListingDetail listingId={listingId} />
    </Suspense>
  );
}
