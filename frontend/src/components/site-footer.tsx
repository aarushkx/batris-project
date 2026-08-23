import Link from "next/link";
import { Logomark } from "@/components/site-header";
import {
  APP_FULL_NAME,
  APP_NAME,
  BUILT_FOR,
  DATA_SOURCE,
  DISCLAIMER,
  FOOTER_SECTIONS,
  TEAM_NAME,
} from "@/lib/constants";

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-mist/50">
      <div className="mx-auto max-w-[1320px] px-5 py-14 sm:px-8">
        <div className="grid gap-10 md:grid-cols-[1.6fr_1fr_1fr]">
          <div className="max-w-sm">
            <div className="flex items-center gap-2.5 text-ink">
              <Logomark />
              <span className="font-display text-[19px] font-bold">{APP_NAME}</span>
            </div>
            <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
              {APP_FULL_NAME}. Built for {BUILT_FOR} by {TEAM_NAME}.
            </p>
            <p className="mt-3 text-[12px] leading-relaxed text-ink-soft">
              Data: {DATA_SOURCE}.
            </p>
          </div>

          {FOOTER_SECTIONS.map((section) => (
            <div key={section.title}>
              <h3 className="eyebrow">{section.title}</h3>
              <ul className="mt-3.5 grid gap-2.5">
                {section.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="text-[13.5px] text-ink-soft transition-colors hover:text-ink"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col gap-3 border-t border-line pt-6 text-[12px] text-ink-soft sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-2xl leading-relaxed">{DISCLAIMER}</p>
          <p className="shrink-0">
            &copy; {new Date().getFullYear()} {TEAM_NAME}
          </p>
        </div>
      </div>
    </footer>
  );
}
