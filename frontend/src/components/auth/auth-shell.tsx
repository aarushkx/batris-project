import Image from "next/image";
import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { APP_FULL_NAME, APP_NAME } from "@/lib/constants";
import { Logomark } from "@/components/site-header";

export function AuthShell({
  eyebrow,
  title,
  body,
  children,
}: {
  eyebrow: string;
  title: string;
  body: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-[calc(100vh-8rem)] bg-paper px-5 py-10 sm:px-8 sm:py-14">
      <div className="mx-auto grid max-w-[1080px] overflow-hidden rounded-2xl border border-line bg-card shadow-[0_22px_70px_rgba(12,16,19,0.08)] lg:grid-cols-[1fr_0.9fr]">
        <div className="grid-paper relative hidden min-h-[620px] border-r border-line p-10 lg:flex lg:flex-col lg:justify-between">
          <div>
            <Link href="/" className="inline-flex items-center gap-2 text-ink">
              <Logomark className="size-7" />
              <span className="font-display text-lg font-bold">{APP_NAME}</span>
            </Link>
            <div className="mt-20 max-w-md">
              <p className="eyebrow">Account layer</p>
              <h1 className="mt-3 font-display text-4xl font-bold leading-[1.04] tracking-[-0.045em]">
                Keep the batteries you care about in one place.
              </h1>
              <p className="mt-5 max-w-sm text-[14px] leading-7 text-ink-soft">
                Sign in to save assessments, passports and the inputs behind them. The public analysis experience remains available without an account.
              </p>
            </div>
          </div>
          <div className="rounded-xl border border-line bg-paper/80 p-4 backdrop-blur">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-estimated" />
              <div>
                <p className="text-[12.5px] font-medium">Designed around verification</p>
                <p className="mt-1 text-[11.5px] leading-relaxed text-ink-soft">
                  Your account is for history and ownership. It does not replace the signed passport or its independent verification.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex min-h-[620px] flex-col p-6 sm:p-10">
          <div className="lg:hidden">
            <Link href="/" className="inline-flex items-center gap-2 text-ink">
              <Image src="/logo.svg" alt="Logo" width={28} height={28} />
              <span className="font-display text-lg font-bold">{APP_NAME}</span>
            </Link>
          </div>

          <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center">
            <Link href="/" className="mb-8 inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-soft hover:text-ink">
              <ArrowLeft className="size-3.5" /> Back to {APP_NAME}
            </Link>
            <p className="eyebrow">{eyebrow}</p>
            <h2 className="mt-2 font-display text-3xl font-bold tracking-[-0.04em]">{title}</h2>
            <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">{body}</p>
            <div className="mt-7">{children}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
