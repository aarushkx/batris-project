"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  Info,
  LogIn,
  RefreshCw,
  Store,
} from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Note, SectionCard } from "@/components/shared/primitives";
import { GradeBadge, gradeMeta } from "@/components/market/shared";
import { publishListing } from "@/lib/api";
import { MARKET } from "@/lib/constants";
import { useAuth } from "@/lib/auth";
import type { Assessment, MarketListing, Passport, UnseenAssessment } from "@/lib/types";

const MAX_NOTES = 600;

export function PublishListingPanel({
  assessment,
  passport,
  id,
}: {
  assessment: Assessment | UnseenAssessment | null;
  passport?: Passport | null;
  id?: string;
}) {
  const { user } = useAuth();
  const router = useRouter();

  const [title, setTitle] = React.useState("");
  const [location, setLocation] = React.useState("");
  const [notes, setNotes] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [published, setPublished] = React.useState<MarketListing | null>(null);

  // A new assessment invalidates whatever was published from the previous one.
  React.useEffect(() => {
    setPublished(null);
  }, [assessment]);

  const grade = assessment?.second_life?.grade ?? null;
  const meta = gradeMeta(grade);
  const gradable = Boolean(meta);

  async function handlePublish() {
    if (!assessment) return;
    if (!user) {
      router.push("/login?next=%2Fdashboard");
      return;
    }
    setBusy(true);
    try {
      const result = await publishListing({
        assessment,
        title: title.trim() || null,
        location: location.trim() || null,
        notes: notes.trim() || null,
        passport: passport ?? null,
      });
      setPublished(result.listing);
      toast.success("Listed on the second-life market", {
        description: "Buyers can now find this battery and contact you by email.",
      });
    } catch (error) {
      toast.error("Could not publish the listing", {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(false);
    }
  }

  if (!assessment) {
    return null;
  }

  /* ------------------------------------------------------------ published */
  if (published) {
    return (
      <SectionCard
        id={id}
        title="Listed on the second-life market"
        description="The listing carries the assessment above, so the numbers a buyer reads are the numbers the model produced."
      >
        <Alert variant="good">
          <Check />
          <AlertTitle>
            {published.battery_id} is live with reuse grade {published.grade}
          </AlertTitle>
          <AlertDescription>
            Your name and email are visible on the listing so buyers can reach you. You
            can withdraw it at any time from your account.
          </AlertDescription>
        </Alert>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button asChild>
            <Link href={`/market/${published.listing_id}`}>
              View the listing <ArrowUpRight />
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/market">Browse the market</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/account#listings">Manage my listings</Link>
          </Button>
        </div>
      </SectionCard>
    );
  }

  /* -------------------------------------------------------------- ungraded */
  if (!gradable) {
    return (
      <SectionCard id={id} title={MARKET.publishTitle}>
        <Alert variant="warn">
          <AlertTriangle />
          <AlertTitle>This assessment cannot be listed</AlertTitle>
          <AlertDescription>
            A listing has to carry a reuse grade, and grades are only issued when the
            input level supports one. Supply richer input — a charge log rather than
            hand-typed figures — and reassess.
          </AlertDescription>
        </Alert>
      </SectionCard>
    );
  }

  /* ------------------------------------------------------------------ form */
  return (
    <SectionCard id={id} title={MARKET.publishTitle} description={MARKET.publishBody}>
      {/* What will be published, derived, not typed */}
      <div className="rounded-xl border border-line bg-mist/50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="eyebrow">Derived from this assessment</p>
            <p className="mt-1.5 text-[13.5px] font-medium">
              {assessment.battery_id} · {assessment.health.soh_percent.toFixed(1)}%
              retained SOH · risk {assessment.safety.risk_band}
            </p>
          </div>
          <GradeBadge grade={grade} />
        </div>
        <p className="mt-2.5 text-[11.5px] leading-relaxed text-ink-soft">
          Health, grade, risk band and confidence interval are copied from the
          assessment and cannot be edited on the listing. You only supply the context
          below.
        </p>
      </div>

      {assessment.second_life.grade === "RECYCLE" ? (
        <Alert variant="warn" className="mt-3">
          <Info />
          <AlertTitle>This pack is graded for material recovery, not reuse</AlertTitle>
          <AlertDescription>
            You can still list it — recyclers use this inventory — but the listing will
            say plainly that it is not suitable for reuse.
          </AlertDescription>
        </Alert>
      ) : null}

      {/* Seller-supplied context */}
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="grid gap-1.5">
          <Label htmlFor="listingTitle" className="eyebrow">
            Listing headline (optional)
          </Label>
          <Input
            id="listingTitle"
            maxLength={90}
            placeholder="e.g. 18650 cell, retired from cycling rig"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="listingLocation" className="eyebrow">
            Location (optional)
          </Label>
          <Input
            id="listingLocation"
            maxLength={80}
            placeholder="e.g. Bengaluru, KA"
            value={location}
            onChange={(event) => setLocation(event.target.value)}
          />
        </div>
      </div>

      <div className="mt-3 grid gap-1.5">
        <Label htmlFor="listingNotes" className="eyebrow">
          What a buyer should know (optional)
        </Label>
        <textarea
          id="listingNotes"
          rows={4}
          maxLength={MAX_NOTES}
          placeholder="Physical condition, what it came out of, how it has been stored, collection or shipping."
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          className="w-full rounded-md border border-line bg-paper px-3 py-2.5 text-[13px] leading-relaxed outline-none transition-[color,box-shadow] placeholder:text-ink-soft/60 focus-visible:ring-[3px] focus-visible:ring-ring/45"
        />
        <p className="text-right text-[10.5px] tabular text-ink-soft/70">
          {notes.length}/{MAX_NOTES}
        </p>
      </div>

      {/* Consent is explicit: publishing reveals contact details. */}
      <div className="mt-4 rounded-lg border border-estimated/25 bg-estimated/6 px-3.5 py-3">
        <p className="text-[12.5px] font-medium">
          {user
            ? `Publishing shows your name (${user.name}) and email (${user.email}) to everyone browsing the market.`
            : "Sign in to publish. Your account name and email become the listing's contact details."}
        </p>
        <p className="mt-1 text-[11.5px] leading-relaxed text-ink-soft">
          There is no pricing or payment on the platform. Buyers email you and you agree
          terms directly.
        </p>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button onClick={() => void handlePublish()} disabled={busy}>
          {busy ? <RefreshCw className="animate-spin" /> : user ? <Store /> : <LogIn />}
          {busy
            ? "Publishing\u2026"
            : user
              ? "Publish to the market"
              : "Sign in to publish"}
        </Button>
        <Button variant="ghost" asChild>
          <Link href="/market">Browse the market</Link>
        </Button>
      </div>

      <div className="mt-3">
        <Note>
          Listing a battery does not certify it. The buyer still sees the confidence
          interval and the recommendation to commission a certified capacity test before
          any warranted resale.
        </Note>
      </div>
    </SectionCard>
  );
}
