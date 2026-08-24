"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Beaker, Database } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { FleetView } from "@/components/dashboard/fleet-view";
import { OwnView } from "@/components/dashboard/own-view";
import { APP_FULL_NAME, APP_TAGLINE, ESTIMATE_BANNER } from "@/lib/constants";

type View = "fleet" | "own";

export function DashboardShell() {
  const router = useRouter();
  const params = useSearchParams();
  const view: View = params.get("view") === "own" ? "own" : "fleet";

  // Both views stay mounted once visited so switching tabs never discards an
  // assessment the user is part-way through reading.
  const [visitedOwn, setVisitedOwn] = React.useState(view === "own");

  function setView(next: string) {
    if (next === "own") setVisitedOwn(true);
    const query = next === "own" ? "?view=own" : "";
    router.replace(`/dashboard${query}`, { scroll: false });
  }

  return (
    <div className="mx-auto max-w-[1320px] px-3 pt-6 pb-16 sm:px-8 sm:pt-8">
      <div className="px-2 sm:px-0">
        <h1 className="font-display text-[clamp(1.8rem,3.4vw,2.5rem)] leading-tight font-bold">
          {APP_FULL_NAME}
        </h1>
        <p className="mt-1.5 text-[13px] text-ink-soft">{APP_TAGLINE}</p>
      </div>

      <Tabs value={view} onValueChange={setView} className="mt-6 gap-4">
        <TabsList className="grid w-full grid-cols-2 sm:inline-flex sm:w-auto">
          <TabsTrigger
            value="fleet"
            className="min-w-0 whitespace-normal px-2 text-center leading-tight sm:px-4"
          >
            <Database />
            Batteries in the dataset
          </TabsTrigger>

          <TabsTrigger
            value="own"
            className="min-w-0 whitespace-normal px-2 text-center leading-tight sm:px-4"
          >
            <Beaker />
            Assess my own battery
          </TabsTrigger>
        </TabsList>

        <Alert variant="estimated">
          <AlertTitle>{ESTIMATE_BANNER.title}</AlertTitle>
          <AlertDescription>{ESTIMATE_BANNER.body}</AlertDescription>
        </Alert>

        <TabsContent value="fleet" forceMount hidden={view !== "fleet"}>
          <FleetView />
        </TabsContent>

        <TabsContent value="own" forceMount hidden={view !== "own"}>
          {visitedOwn ? <OwnView /> : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
