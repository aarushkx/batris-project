import { Suspense } from "react";
import type { Metadata } from "next";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-[1320px] px-5 py-10 sm:px-8">
          <Skeleton className="h-72 rounded-xl" />
        </div>
      }
    >
      <DashboardShell />
    </Suspense>
  );
}
