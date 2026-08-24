"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, LogIn, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "@/components/auth/auth-shell";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const requestedNext = params.get("next") || "/account";
  const next = requestedNext.startsWith("/") && !requestedNext.startsWith("//") ? requestedNext : "/account";
  const { user, login, loading } = useAuth();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, next, router, user]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      router.replace(next);
    } catch (error) {
      toast.error("Could not sign in", {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Sign in"
      title="Welcome back."
      body="Access the assessments and second-life passports you have chosen to keep with BATRIS."
    >
      <form onSubmit={handleSubmit} className="grid gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor="login-email">Email</Label>
          <Input id="login-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="johndoe@example.com" required />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="login-password">Password</Label>
          <div className="relative">
            <Input id="login-password" type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className="pr-11" required />
            <button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((v) => !v)} className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-ink-soft hover:bg-mist hover:text-ink">
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </div>
        <Button type="submit" className="mt-1 w-full" disabled={busy}>
          {busy ? <RefreshCw className="animate-spin" /> : <LogIn />}
          {busy ? "Signing in…" : "Sign in"}
        </Button>
        <p className="text-center text-[12.5px] text-ink-soft">
          New to BATRIS?{" "}
          <Link href={`/register?next=${encodeURIComponent(next)}`} className="font-medium text-ink underline decoration-line underline-offset-4">
            Create an account
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
