import { Suspense } from "react";
import type { Metadata } from "next";
import { MarketShell } from "@/components/market/market-shell";
import { Skeleton } from "@/components/ui/skeleton";
import { MARKET } from "@/lib/constants";

export const metadata: Metadata = {
  title: "Second-life market",
  description: MARKET.body,
};

export default function MarketPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-[1320px] px-5 py-10 sm:px-8">
          <Skeleton className="h-72 rounded-xl" />
        </div>
      }
    >
      <MarketShell />
    </Suspense>
  );
}
