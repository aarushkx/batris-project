import { Suspense } from "react";
import type { Metadata } from "next";
import { BenchmarkShell } from "@/components/benchmark/benchmark-shell";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Model Benchmark" };

export default function BenchmarkPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-[1320px] px-5 py-10 sm:px-8">
          <Skeleton className="h-72 rounded-xl" />
        </div>
      }
    >
      <BenchmarkShell />
    </Suspense>
  );
}
