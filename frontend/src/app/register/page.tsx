"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Eye, EyeOff, RefreshCw, UserRoundPlus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "@/components/auth/auth-shell";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const params = useSearchParams();
  const requestedNext = params.get("next") || "/account";
  const next = requestedNext.startsWith("/") && !requestedNext.startsWith("//") ? requestedNext : "/account";
  const { user, register, loading } = useAuth();
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, next, router, user]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password.length < 8) {
      toast.error("Use a longer password", { description: "Your password needs at least 8 characters." });
      return;
    }
    setBusy(true);
    try {
      await register(name, email, password);
      router.replace(next);
    } catch (error) {
      toast.error("Could not create the account", {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Create account"
      title="Make your history portable."
      body="Your account gives your battery work a place to persist. The analysis itself remains useful without signing in."
    >
      <form onSubmit={handleSubmit} className="grid gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor="register-name">Name</Label>
          <Input id="register-name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="John Doe" required />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="register-email">Email</Label>
          <Input id="register-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="johndoe@example.com" required />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="register-password">Password</Label>
          <div className="relative">
            <Input id="register-password" type={showPassword ? "text" : "password"} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} className="pr-11" required />
            <button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((v) => !v)} className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-ink-soft hover:bg-mist hover:text-ink">
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          <p className="text-[11.5px] text-ink-soft">At least 8 characters.</p>
        </div>
        <Button type="submit" className="mt-1 w-full" disabled={busy}>
          {busy ? <RefreshCw className="animate-spin" /> : <UserRoundPlus />}
          {busy ? "Creating account…" : "Create account"}
        </Button>
        <p className="text-center text-[12.5px] text-ink-soft">
          Already have an account?{" "}
          <Link href={`/login?next=${encodeURIComponent(next)}`} className="inline-flex items-center gap-1 font-medium text-ink underline decoration-line underline-offset-4">
            Sign in <ArrowRight className="size-3" />
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
