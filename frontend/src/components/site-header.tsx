"use client";

import * as React from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X, LogIn, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { APP_NAME, NAV_LINKS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

export function Logomark({ className }: { className?: string }) {
  return (
    <Image
      src="/logo.svg"
      alt="Logo"
      width={32}
      height={32}
      className={cn("size-8 object-contain", className)}
    />
  );
}

export function SiteHeader() {
  const [open, setOpen] = React.useState(false);
  const [scrolled, setScrolled] = React.useState(false);
  const pathname = usePathname();
  const { user, loading, logout } = useAuth();

  React.useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  React.useEffect(() => setOpen(false), [pathname]);

  const onDashboard = pathname.startsWith("/dashboard");

  return (
    <header
      className={cn(
        "sticky top-0 z-50 border-b transition-colors duration-200",
        scrolled
          ? "border-line bg-paper/85 backdrop-blur-xl"
          : "border-transparent bg-paper",
      )}
    >
      <div className="mx-auto flex h-16 max-w-[1320px] items-center justify-between gap-6 px-5 sm:px-8">
        <Link href="/" className="flex items-center gap-1 text-ink">
          <Logomark />
          <span className="font-display text-[19px] font-bold">{APP_NAME}</span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-full px-3.5 py-2 text-[13.5px] font-medium text-ink-soft transition-colors hover:bg-mist hover:text-ink"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          {!onDashboard && (
            <Button variant="ghost" size="sm" asChild>
              <Link href="/dashboard?view=own">Assess my battery</Link>
            </Button>
          )}
          <Button size="sm" asChild>
            <Link href="/dashboard">{onDashboard ? "Fleet dashboard" : "Open dashboard"}</Link>
          </Button>
          {!loading && user ? (
            <Button variant="outline" size="sm" asChild>
              <Link href="/account"><UserRound /> My account</Link>
            </Button>
          ) : (
            <Button variant="outline" size="sm" asChild>
              <Link href="/login"><LogIn /> Sign in</Link>
            </Button>
          )}
        </div>

        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex size-9 cursor-pointer items-center justify-center rounded-full border border-line md:hidden"
        >
          {open ? <X className="size-4" /> : <Menu className="size-4" />}
        </button>
      </div>

      {open ? (
        <div className="border-t border-line bg-paper px-5 pb-5 md:hidden">
          <nav className="grid gap-0.5 py-2">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="rounded-lg px-3 py-2.5 text-[14px] font-medium text-ink-soft hover:bg-mist hover:text-ink"
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="grid gap-2">
            <Button asChild>
              <Link href="/dashboard">Open dashboard</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/dashboard?view=own">Assess my battery</Link>
            </Button>
            {!loading && user ? (
              <>
                <Button variant="outline" asChild><Link href="/account"><UserRound /> My account</Link></Button>
                <Button variant="ghost" onClick={() => void logout()}><LogIn /> Sign out</Button>
              </>
            ) : (
              <Button variant="outline" asChild><Link href="/login"><LogIn /> Sign in</Link></Button>
            )}
          </div>
        </div>
      ) : null}
    </header>
  );
}
