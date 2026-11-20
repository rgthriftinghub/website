"use client";

import { Heart, LogOut, MapPin, Package, ShieldCheck, ShoppingBag } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { errorMessage, useStore } from "@/components/providers/store-provider";
import { Button } from "@/components/ui/button";
import { login, register } from "@/lib/api/catalog";
import { cn } from "@/lib/utils";

type Mode = "login" | "register";

function Field({
  label,
  name,
  type = "text",
  required = true,
  autoComplete,
}: {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  autoComplete?: string;
}) {
  return (
    <label className="block">
      <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
        {label}
      </span>
      <input
        name={name}
        type={type}
        required={required}
        autoComplete={autoComplete}
        className="mt-1.5 h-11 w-full border border-line bg-surface px-3 text-sm text-ink outline-none transition-colors focus:border-gold"
      />
    </label>
  );
}

const ACCOUNT_LINKS = [
  { href: "/account/orders", label: "Your orders", blurb: "Track and manage past orders", icon: Package },
  { href: "/account/addresses", label: "Addresses", blurb: "Manage delivery addresses", icon: MapPin },
  { href: "/wishlist", label: "Wishlist", blurb: "Pieces you have saved", icon: Heart },
  { href: "/cart", label: "Your bag", blurb: "Items ready to check out", icon: ShoppingBag },
];

/** Suspense boundary: `useSearchParams` opts a component out of prerendering. */
export function AccountPanel() {
  return (
    <Suspense fallback={<div className="mt-10 h-64 border border-line" />}>
      <AccountPanelInner />
    </Suspense>
  );
}

function AccountPanelInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isLoading, refreshSession, signOut } = useStore();

  const [mode, setMode] = useState<Mode>("login");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const nextParam = searchParams.get("next");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);

    try {
      if (mode === "login") {
        await login({
          email: String(form.get("email")),
          password: String(form.get("password")),
        });
      } else {
        await register({
          email: String(form.get("email")),
          password: String(form.get("password")),
          first_name: String(form.get("first_name")),
          last_name: String(form.get("last_name")),
          phone: String(form.get("phone") ?? "") || undefined,
        });
      }
      // Pulls the session, bag, and wishlist into shared state in one go.
      await refreshSession();

      // Only in-app paths are followed, so `next` cannot be used to bounce a
      // signed-in customer to another site.
      if (nextParam && nextParam.startsWith("/")) {
        router.push(nextParam);
      }
    } catch (caught) {
      setError(errorMessage(caught, "Something went wrong. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) {
    return (
      <p className="mt-10 text-center text-sm text-stone" role="status">
        Checking your session…
      </p>
    );
  }

  if (user) {
    return (
      <div className="mt-10">
        <div className="border border-line bg-surface p-7">
          <p className="eyebrow">Signed in</p>
          <h2 className="mt-2 font-display text-2xl">
            {user.first_name} {user.last_name}
          </h2>
          <p className="mt-1 text-sm text-ink-muted">{user.email}</p>

          {user.role !== "CUSTOMER" ? (
            <Link
              href="/admin"
              className="mt-5 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-gold-deep hover:text-ink"
            >
              <ShieldCheck className="size-4" aria-hidden />
              Open the admin area
            </Link>
          ) : null}
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {ACCOUNT_LINKS.map(({ href, label, blurb, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="group border border-line bg-surface p-5 transition-colors hover:border-gold"
            >
              <Icon className="size-4 text-gold-deep" aria-hidden />
              <p className="mt-3 font-display text-lg text-ink">{label}</p>
              <p className="mt-0.5 text-xs text-ink-muted">{blurb}</p>
            </Link>
          ))}
        </div>

        <Button
          variant="secondary"
          className="mt-5 w-full"
          onClick={async () => {
            await signOut();
            router.push("/");
          }}
        >
          <LogOut className="size-4" aria-hidden />
          Sign out
        </Button>
      </div>
    );
  }

  return (
    <div className="mt-10">
      {nextParam ? (
        <p className="mb-5 border border-gold/40 bg-gold-wash px-4 py-3 text-xs text-ink">
          Sign in to continue.
        </p>
      ) : null}

      <div className="grid grid-cols-2 border border-line">
        {(["login", "register"] as Mode[]).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => {
              setMode(option);
              setError(null);
            }}
            className={cn(
              "py-3 text-[11px] font-semibold uppercase tracking-[0.12em] transition-colors",
              mode === option ? "bg-ink text-paper" : "bg-surface text-ink-muted hover:bg-paper-alt"
            )}
          >
            {option === "login" ? "Sign in" : "Create account"}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4 border border-line bg-surface p-6">
        {mode === "register" ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="First name" name="first_name" autoComplete="given-name" />
              <Field label="Last name" name="last_name" autoComplete="family-name" />
            </div>
            <Field label="Phone (optional)" name="phone" required={false} autoComplete="tel" />
          </>
        ) : null}

        <Field label="Email" name="email" type="email" autoComplete="email" />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
        />

        {mode === "register" ? (
          <p className="text-xs text-stone">Use at least 8 characters.</p>
        ) : null}

        {error ? (
          <p role="alert" className="border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
            {error}
          </p>
        ) : null}

        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </Button>
      </form>
    </div>
  );
}
