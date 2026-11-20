"use client";

import { Lock } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { ButtonLink } from "@/components/ui/button";
import { getCurrentUser } from "@/lib/api/catalog";
import type { User } from "@/lib/api/types";

type State = { status: "checking" } | { status: "allowed"; user: User } | { status: "denied" };

/**
 * Client-side guard for the admin shell.
 *
 * This is a usability measure, not the security boundary: every admin endpoint
 * independently requires an ADMIN or STAFF role on the server, so hiding the UI
 * cannot be the only thing standing between a customer and the data.
 */
export function AdminGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: "checking" });

  useEffect(() => {
    getCurrentUser()
      .then((user) =>
        setState(
          user.role === "ADMIN" || user.role === "STAFF"
            ? { status: "allowed", user }
            : { status: "denied" }
        )
      )
      .catch(() => setState({ status: "denied" }));
  }, []);

  if (state.status === "checking") {
    return (
      <div className="grid flex-1 place-items-center py-24">
        <p className="text-sm text-stone" role="status">
          Checking your permissions…
        </p>
      </div>
    );
  }

  if (state.status === "denied") {
    return (
      <div className="grid flex-1 place-items-center px-4 py-24">
        <div className="max-w-md border border-line bg-paper p-8 text-center">
          <Lock className="mx-auto size-6 text-gold-deep" aria-hidden />
          <h1 className="mt-4 font-display text-2xl">Staff access only</h1>
          <p className="mt-2.5 text-sm text-ink-muted">
            Sign in with an admin or staff account to manage the catalogue.
          </p>
          <ButtonLink href="/account" className="mt-7">
            Go to sign in
          </ButtonLink>
          <Link
            href="/"
            className="mt-5 block text-xs font-semibold uppercase tracking-[0.12em] text-stone hover:text-ink"
          >
            Back to store
          </Link>
        </div>
      </div>
    );
  }

  return (
    <>
      <p className="mx-auto w-full max-w-7xl px-4 pt-6 text-xs text-stone sm:px-6 lg:px-8">
        Signed in as {state.user.first_name} {state.user.last_name} · {state.user.role}
      </p>
      {children}
    </>
  );
}
