// "use client";

// import * as React from "react";
// import { useRouter } from "next/navigation";
// import { ArrowUpRight, FileSignature, LogOut, ShieldCheck } from "lucide-react";
// import { toast } from "sonner";
// import { Button } from "@/components/ui/button";
// import { Badge } from "@/components/ui/badge";
// import { SectionCard, KeyValue, KeyValueGrid } from "@/components/shared/primitives";
// import { getAccountHistory, useAuth } from "@/lib/auth";

// export default function AccountPage() {
//   const router = useRouter();
//   const { user, loading, logout } = useAuth();
//   const [history, setHistory] = React.useState<{ assessments: Array<Record<string, any>>; passports: Array<Record<string, any>> } | null>(null);
//   const [busy, setBusy] = React.useState(true);

//   React.useEffect(() => {
//     if (loading) return;
//     if (!user) {
//       router.replace("/login?next=%2Faccount");
//       return;
//     }
//     getAccountHistory()
//       .then(setHistory)
//       .catch((error) => toast.error("Could not load account history", { description: error instanceof Error ? error.message : String(error) }))
//       .finally(() => setBusy(false));
//   }, [loading, router, user]);

//   async function handleLogout() {
//     await logout();
//     router.replace("/");
//   }

//   if (loading || !user || busy) {
//     return <div className="mx-auto max-w-[1100px] px-5 py-16 text-sm text-ink-soft">Loading your account…</div>;
//   }

//   return (
//     <div className="mx-auto max-w-[1100px] px-5 py-10 sm:px-8 sm:py-14">
//       <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
//         <div>
//           <p className="eyebrow">My BATRIS</p>
//           <h1 className="mt-1 font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-[-0.045em]">{user.name}</h1>
//           <p className="mt-2 text-[13px] text-ink-soft">{user.email}</p>
//         </div>
//         <Button variant="outline" onClick={handleLogout}><LogOut /> Sign out</Button>
//       </div>

//       <div className="mt-8 grid gap-3 sm:grid-cols-3">
//         <SectionCard title="Assessments" description="Saved analysis snapshots">
//           <p className="tabular font-display text-3xl font-bold">{history?.assessments.length ?? 0}</p>
//         </SectionCard>
//         <SectionCard title="Passports" description="Signed documents saved to your account">
//           <p className="tabular font-display text-3xl font-bold">{history?.passports.length ?? 0}</p>
//         </SectionCard>
//         <SectionCard title="Account" description="Your identity is separate from passport trust">
//           <div className="flex items-center gap-2 text-[13px] font-medium"><ShieldCheck className="size-4 text-estimated" /> Verified session</div>
//         </SectionCard>
//       </div>

//       <div className="mt-3 grid gap-3 lg:grid-cols-2">
//         <SectionCard title="Saved assessments" description="The result and non-file inputs you chose to keep.">
//           {history?.assessments.length ? (
//             <div className="grid gap-2">
//               {history.assessments.map((item) => {
//                 const health = item.assessment?.health;
//                 return (
//                   <div key={item.id} className="rounded-xl border border-line bg-mist/40 p-3.5">
//                     <div className="flex items-start justify-between gap-3">
//                       <div>
//                         <p className="text-[13px] font-medium">{item.battery_id}</p>
//                         <p className="mt-1 text-[11.5px] text-ink-soft">{item.input_mode} · {item.format_key ?? "default format"}</p>
//                       </div>
//                       {health?.soh_percent != null ? <Badge variant="estimated">{health.soh_percent.toFixed(1)}% SOH</Badge> : null}
//                     </div>
//                     <p className="mt-2 text-[11px] text-ink-soft">Saved {new Date(item.created_at).toLocaleString()}</p>
//                   </div>
//                 );
//               })}
//             </div>
//           ) : (
//             <p className="text-[12.5px] text-ink-soft">Nothing saved yet. Run an assessment and choose “Save to my account”.</p>
//           )}
//         </SectionCard>

//         <SectionCard title="Saved passports" description="Portable records you can keep alongside your assessments.">
//           {history?.passports.length ? (
//             <div className="grid gap-2">
//               {history.passports.map((item) => {
//                 const passport = item.passport?.payload;
//                 return (
//                   <div key={item.passport_id} className="rounded-xl border border-line bg-mist/40 p-3.5">
//                     <div className="flex items-start justify-between gap-3">
//                       <div>
//                         <p className="text-[13px] font-medium">{item.battery_id ?? "Battery"}</p>
//                         <p className="mt-1 break-all font-mono text-[10.5px] text-ink-soft">{item.passport_id}</p>
//                       </div>
//                       <FileSignature className="size-4 text-estimated" />
//                     </div>
//                     <div className="mt-3 grid grid-cols-2 gap-2">
//                       <KeyValue small label="SOH" value={passport?.health_estimate?.soh_percent != null ? `${passport.health_estimate.soh_percent}%` : "—"} />
//                       <KeyValue small label="Grade" value={passport?.second_life_assessment?.grade ?? "—"} />
//                     </div>
//                     <p className="mt-3 text-[11px] text-ink-soft">Saved {new Date(item.created_at).toLocaleString()}</p>
//                   </div>
//                 );
//               })}
//             </div>
//           ) : (
//             <p className="text-[12.5px] text-ink-soft">No signed passports saved yet. Issue one from an assessment and save it from the passport panel.</p>
//           )}
//         </SectionCard>
//       </div>

//       <div className="mt-6 flex flex-wrap gap-2">
//         <Button onClick={() => router.push("/dashboard?view=own")}>Assess a battery <ArrowUpRight /></Button>
//         <Button variant="outline" onClick={() => router.push("/dashboard")}>Open fleet dashboard</Button>
//       </div>
//     </div>
//   );
// }

"use client";

import * as React from "react";
import {
  ArrowUpRight,
  Download,
  Eye,
  FileSignature,
  FileText,
  LogOut,
  ShieldCheck,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { JsonBlock } from "@/components/shared/analysis";
import { SectionCard, KeyValue } from "@/components/shared/primitives";
import { downloadPassportPdf } from "@/lib/api";
import { downloadJSON } from "@/lib/format";
import { getAccountHistory, useAuth } from "@/lib/auth";
import type { Passport } from "@/lib/types";

type HistoryItem = Record<string, any>;

type DetailModalProps = {
  title: string;
  eyebrow: string;
  onClose: () => void;
  children: React.ReactNode;
  actions?: React.ReactNode;
};

function DetailModal({ title, eyebrow, onClose, children, actions }: DetailModalProps) {
  React.useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) onClose();
      }}
    >
      <div className="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-line bg-paper shadow-[0_24px_70px_rgba(12,16,19,0.18)]">
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4 sm:px-6">
          <div className="min-w-0">
            <p className="eyebrow">{eyebrow}</p>
            <h2 className="mt-1 font-display text-xl font-bold tracking-[-0.03em]">{title}</h2>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            <X />
          </Button>
        </div>
        <div className="min-h-0 overflow-y-auto px-5 py-5 sm:px-6">{children}</div>
        {actions ? <div className="flex flex-wrap gap-2 border-t border-line px-5 py-4 sm:px-6">{actions}</div> : null}
      </div>
    </div>
  );
}

export default function AccountPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [history, setHistory] = React.useState<{ assessments: HistoryItem[]; passports: HistoryItem[] } | null>(null);
  const [busy, setBusy] = React.useState(true);
  const [selectedAssessment, setSelectedAssessment] = React.useState<HistoryItem | null>(null);
  const [selectedPassport, setSelectedPassport] = React.useState<HistoryItem | null>(null);
  // const [passportBusy, setPassportBusy] = React.useState<"json" | "pdf" | null>(null);
  const [passportBusy, setPassportBusy] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login?next=%2Faccount");
      return;
    }
    getAccountHistory()
      .then(setHistory)
      .catch((error) =>
        toast.error("Could not load account history", {
          description: error instanceof Error ? error.message : String(error),
        }),
      )
      .finally(() => setBusy(false));
  }, [loading, router, user]);

  async function handleLogout() {
    await logout();
    router.replace("/");
  }

  function handleDownloadPassportJson(item: HistoryItem) {
    const passport = item.passport as Passport | undefined;
    if (!passport) return;
    const batteryId = passport.payload?.battery?.battery_id ?? item.battery_id ?? "battery";
    downloadJSON(passport, `passport_${batteryId}.json`);
  }

  // async function handleDownloadPassportPdf(item: HistoryItem) {
  //   const passport = item.passport as Passport | undefined;
  //   if (!passport) return;

  //   const batteryId = passport.payload?.battery?.battery_id ?? item.battery_id ?? "battery";
  //   setPassportBusy("pdf");
  //   try {
  //     await downloadPassportPdf(passport, `passport_${batteryId}.pdf`);
  //     toast.success("Passport PDF downloaded");
  //   } catch (error) {
  //     toast.error("Could not download passport PDF", {
  //       description: error instanceof Error ? error.message : String(error),
  //     });
  //   } finally {
  //     setPassportBusy(null);
  //   }
  // }
  async function handleDownloadPassportPdf(item: HistoryItem) {
    const passport = item.passport as Passport | undefined;
    if (!passport) return;

    const passportId = String(item.passport_id ?? "");
    const batteryId =
      passport.payload?.battery?.battery_id ?? item.battery_id ?? "battery";

    setPassportBusy(passportId);

    try {
      await downloadPassportPdf(passport, `passport_${batteryId}.pdf`);
      toast.success("Passport PDF downloaded");
    } catch (error) {
      toast.error("Could not download passport PDF", {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setPassportBusy(null);
    }
}

  if (loading || !user || busy) {
    return <div className="mx-auto max-w-[1100px] px-5 py-16 text-sm text-ink-soft">Loading your account…</div>;
  }

  const assessments = history?.assessments ?? [];
  const passports = history?.passports ?? [];

  return (
    <div className="mx-auto max-w-[1100px] px-5 py-10 sm:px-8 sm:py-14">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow">My BATRIS</p>
          <h1 className="mt-1 font-display text-[clamp(2rem,4vw,3rem)] font-bold tracking-[-0.045em]">{user.name}</h1>
          <p className="mt-2 text-[13px] text-ink-soft">{user.email}</p>
        </div>
        <Button variant="outline" onClick={handleLogout}   className="border-red-200/80 bg-red-100/60 text-red-700 hover:border-red-300 hover:bg-red-50 hover:text-red-800"><LogOut /> Sign out</Button>
      </div>

      <div className="mt-8 grid gap-3 sm:grid-cols-3">
        <SectionCard title="Assessments" description="Saved analysis snapshots">
          <p className="tabular font-display text-3xl font-bold">{assessments.length}</p>
        </SectionCard>
        <SectionCard title="Passports" description="Signed documents saved to your account">
          <p className="tabular font-display text-3xl font-bold">{passports.length}</p>
        </SectionCard>
        <SectionCard title="Account" description="Your identity is separate from passport trust">
          <div className="flex items-center gap-2 text-[13px] font-medium"><ShieldCheck className="size-4 text-estimated" /> Verified session</div>
        </SectionCard>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <SectionCard
          title="Saved assessments"
          description="Open any saved result without rerunning the assessment."
        >
          {assessments.length ? (
            <div className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
              {assessments.map((item) => {
                const health = item.assessment?.health;
                return (
                  <div key={item.id} className="rounded-xl border border-line bg-mist/40 p-3.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-[13px] font-medium">{item.battery_id}</p>
                        <p className="mt-1 truncate text-[11.5px] text-ink-soft">{item.input_mode} · {item.format_key ?? "default format"}</p>
                      </div>
                      {health?.soh_percent != null ? <Badge variant="estimated">{health.soh_percent.toFixed(1)}% SOH</Badge> : null}
                    </div>
                    <p className="mt-2 text-[11px] text-ink-soft">Saved {new Date(item.created_at).toLocaleString()}</p>
                    <div className="mt-3">
                      <Button size="sm" variant="outline" onClick={() => setSelectedAssessment(item)}>
                        <Eye /> View assessment
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-[12.5px] text-ink-soft">Nothing saved yet. Run an assessment and choose “Save to my account”.</p>
          )}
        </SectionCard>

        <SectionCard
          title="Saved passports"
          description="Reopen, download, or regenerate the PDF for any saved passport."
        >
          {passports.length ? (
            <div className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
              {passports.map((item) => {
                const passport = item.passport?.payload;
                return (
                  <div key={item.passport_id} className="rounded-xl border border-line bg-mist/40 p-3.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-[13px] font-medium">{item.battery_id ?? "Battery"}</p>
                        <p className="mt-1 break-all font-mono text-[10.5px] text-ink-soft">{item.passport_id}</p>
                      </div>
                      <FileSignature className="size-4 shrink-0 text-estimated" />
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <KeyValue small label="SOH" value={passport?.health_estimate?.soh_percent != null ? `${passport.health_estimate.soh_percent}%` : "—"} />
                      <KeyValue small label="Grade" value={passport?.second_life_assessment?.grade ?? "—"} />
                    </div>
                    <p className="mt-3 text-[11px] text-ink-soft">Saved {new Date(item.created_at).toLocaleString()}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={() => setSelectedPassport(item)}>
                        <Eye /> View
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleDownloadPassportJson(item)}>
                        <Download /> JSON
                      </Button>
                      {/* <Button size="sm" variant="outline" onClick={() => void handleDownloadPassportPdf(item)} disabled={passportBusy === "pdf"}>
                        <FileText /> {passportBusy === "pdf" ? "Preparing…" : "PDF"}
                      </Button> */}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => void handleDownloadPassportPdf(item)}
                        disabled={passportBusy === String(item.passport_id)}
                      >
                        <FileText />
                        {passportBusy === String(item.passport_id) ? "Preparing…" : "PDF"}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-[12.5px] text-ink-soft">No signed passports saved yet. Issue one from an assessment and save it from the passport panel.</p>
          )}
        </SectionCard>
      </div>

      <div className="mt-3 text-[11.5px] text-ink-soft">Showing the 25 most recent saved items in each section.</div>

      <div className="mt-6 flex flex-wrap gap-2">
        <Button onClick={() => router.push("/dashboard?view=own")}>Assess a battery <ArrowUpRight /></Button>
        <Button variant="outline" onClick={() => router.push("/dashboard")}>Open fleet dashboard</Button>
      </div>

      {selectedAssessment ? (
        <DetailModal
          eyebrow="Saved assessment"
          title={selectedAssessment.battery_id ?? "Battery assessment"}
          onClose={() => setSelectedAssessment(null)}
        >
          <div className="mb-4 grid gap-2 sm:grid-cols-3">
            <KeyValue label="SOH" value={selectedAssessment.assessment?.health?.soh_percent != null ? `${selectedAssessment.assessment.health.soh_percent}%` : "—"} />
            <KeyValue label="Grade" value={selectedAssessment.assessment?.second_life?.grade ?? "—"} />
            <KeyValue label="Saved" value={new Date(selectedAssessment.created_at).toLocaleString()} />
          </div>
          <JsonBlock data={selectedAssessment.assessment} />
        </DetailModal>
      ) : null}

      {selectedPassport ? (
        <DetailModal
          eyebrow="Saved passport"
          title={selectedPassport.battery_id ?? "Battery passport"}
          onClose={() => setSelectedPassport(null)}
          actions={
            <>
              <Button variant="outline" onClick={() => handleDownloadPassportJson(selectedPassport)}>
                <Download /> Download JSON
              </Button>
              {/* <Button onClick={() => void handleDownloadPassportPdf(selectedPassport)} disabled={passportBusy === "pdf"}>
                <FileText /> {passportBusy === "pdf" ? "Preparing PDF…" : "Download PDF"}
              </Button> */}
              <Button
                onClick={() => void handleDownloadPassportPdf(selectedPassport)}
                disabled={passportBusy === String(selectedPassport.passport_id)}
              >
                <FileText />
                {passportBusy === String(selectedPassport.passport_id)
                  ? "Preparing PDF…"
                  : "Download PDF"}
              </Button>
            </>
          }
        >
          <div className="mb-4 grid gap-2 sm:grid-cols-3">
            <KeyValue
              label="SOH"
              value={selectedPassport.passport?.payload?.health_estimate?.soh_percent != null ? `${selectedPassport.passport.payload.health_estimate.soh_percent}%` : "—"}
            />
            <KeyValue label="Grade" value={selectedPassport.passport?.payload?.second_life_assessment?.grade ?? "—"} />
            <KeyValue label="Saved" value={new Date(selectedPassport.created_at).toLocaleString()} />
          </div>
          <JsonBlock data={selectedPassport.passport} />
        </DetailModal>
      ) : null}
    </div>
  );
}
