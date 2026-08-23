"use client";

import * as React from "react";
import { QRCodeSVG } from "qrcode.react";
import { Download, FileSignature, QrCode, ShieldCheck, Wrench } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { JsonBlock, VerifyBox } from "@/components/shared/analysis";
import { Note, SectionCard } from "@/components/shared/primitives";
import { issuePassportPdf, verifyPassport } from "@/lib/api";
import { downloadJSON } from "@/lib/format";
import type { Passport, PassportPdf, VerifyResult } from "@/lib/types";

export function PassportPanel({
  nextStep,
  issue,
  allowTamper = false,
  id,
}: {
  nextStep?: string;
  issue: () => Promise<Passport>;
  allowTamper?: boolean;
  id?: string;
}) {
  const [passport, setPassport] = React.useState<Passport | null>(null);
  const [verification, setVerification] = React.useState<{
    result: VerifyResult;
    context: string;
  } | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [pdf, setPdf] = React.useState<PassportPdf | null>(null);

  // A new assessment invalidates whatever was issued for the previous one.
  const reset = React.useCallback(() => {
    setPassport(null);
    setVerification(null);
    setPdf(null);
  }, []);

  React.useEffect(() => {
    reset();
  }, [issue, reset]);

  async function handleIssue() {
    setBusy("issue");
    try {
      const document = await issue();
      setPassport(document);
      setVerification(null);
      setPdf(null);
      toast.success("Passport issued", {
        description: "Signed with the issuer's Ed25519 key.",
      });
    } catch (error) {
      toast.error("Could not issue the passport", {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(null);
    }
  }

  async function runVerify(document: Passport, context: string) {
    try {
      const result = await verifyPassport(document);
      setVerification({ result, context });
    } catch (error) {
      toast.error("Verification failed to run", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  }

  async function handleVerify() {
    if (!passport) return;
    setBusy("verify");
    await runVerify(passport, "Verified against the issuer's public key file.");
    setBusy(null);
  }

  async function handleTamper() {
    if (!passport) return;
    setBusy("tamper");
    // Deep copy, then alter a single health figure — the change an
    // unscrupulous reseller would make, leaving the signature untouched.
    const forged = JSON.parse(JSON.stringify(passport)) as Passport;
    const original = forged.payload.health_estimate.soh_percent;
    forged.payload.health_estimate.soh_percent = 97.5;
    forged.payload.health_estimate.soh = 0.975;
    forged.payload.second_life_assessment.grade = "A";
    await runVerify(
      forged,
      `Altered SOH from ${original}% to 97.5% and upgraded the reuse grade to A, leaving the signature untouched.`,
    );
    setBusy(null);
  }

  function handleDownload() {
    if (!passport) return;
    const batteryId = passport.payload.battery.battery_id ?? "battery";
    downloadJSON(passport, `passport_${batteryId}.json`);
  }

  async function handleGetPdf() {
    if (!passport) return;
    setBusy("pdf");
    try {
      const result = await issuePassportPdf(passport);
      setPdf(result);
    } catch (error) {
      toast.error("Could not prepare the PDF", {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(null);
    }
  }

  const pdfUrl =
    pdf && typeof window !== "undefined"
      ? new URL(pdf.pdf_url, window.location.origin).toString()
      : null;

  return (
    <SectionCard
      id={id}
      title="Second-life passport"
      description={nextStep}
    >
      <div className="flex flex-wrap gap-2">
        <Button onClick={handleIssue} disabled={busy === "issue"}>
          <FileSignature />
          {busy === "issue" ? "Signing\u2026" : "Issue signed passport"}
        </Button>
        <Button variant="outline" onClick={handleVerify} disabled={!passport || busy === "verify"}>
          <ShieldCheck />
          Verify signature
        </Button>
        {allowTamper && (
          <Button
            variant="outline"
            onClick={handleTamper}
            disabled={!passport || busy === "tamper"}
          >
            <Wrench />
            Tamper &amp; re-verify
          </Button>
        )}
        <Button variant="outline" onClick={handleDownload} disabled={!passport}>
          <Download />
          Download JSON
        </Button>
        <Button variant="outline" onClick={handleGetPdf} disabled={!passport || busy === "pdf"}>
          <QrCode />
          {busy === "pdf" ? "Preparing PDF\u2026" : "Get PDF & QR"}
        </Button>
      </div>

      {!passport && !verification ? (
        <div className="mt-4">
          <Note>
            Nothing signed yet. Issuing produces a portable JSON document carrying the
            assessment, the model provenance and an explicit label stating that the
            health figure was estimated rather than measured.
          </Note>
        </div>
      ) : null}

      {verification ? (
        <div className="mt-4">
          <VerifyBox result={verification.result} context={verification.context} />
        </div>
      ) : null}

      {pdf && pdfUrl ? (
        <div className="mt-4 flex flex-wrap items-center gap-4 rounded-xl border border-line bg-mist/60 p-4">
          <div className="rounded-lg border border-line bg-card p-2.5">
            <QRCodeSVG value={pdfUrl} size={112} level="M" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="eyebrow">Scan for the PDF</p>
            <p className="mt-1 text-[12.5px] leading-snug text-ink-soft">
              Points to a signed copy of this passport rendered as a PDF, hosted
              at the address below.
            </p>
            <a
              href={pdfUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-2 block truncate text-[12.5px] font-medium text-estimated underline underline-offset-2"
            >
              {pdfUrl}
            </a>
          </div>
        </div>
      ) : null}

      {passport ? (
        <div className="mt-4">
          <JsonBlock data={passport} />
        </div>
      ) : null}
    </SectionCard>
  );
}
