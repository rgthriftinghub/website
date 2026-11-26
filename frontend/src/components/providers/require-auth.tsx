"use client";

import { Lock } from "lucide-react";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useStore } from "@/components/providers/store-provider";
import { ButtonLink } from "@/components/ui/button";

/**
 * Gate for customer-only pages.
 *
 * A usability measure, not the security boundary: every endpoint behind these
 * pages independently requires a session and scopes its queries to the
 * requesting user, so hiding the UI is never the only protection.
 */
export function RequireAuth({
  children,
  title = "Please sign in",
  description = "Sign in to continue.",
}: {
  children: ReactNode;
  title?: string;
  description?: string;
}) {
  const { isAuthenticated, isLoading } = useStore();
  const pathname = usePathname();

  if (isLoading) {
    return (
      <div className="grid place-items-center py-28">
        <p className="text-sm text-stone" role="status">
          Loading…
        </p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <Lock className="mx-auto size-6 text-gold-deep" aria-hidden />
        <h1 className="mt-5 font-display text-3xl">{title}</h1>
        <p className="mt-3 text-sm text-ink-muted">{description}</p>
        <div className="mt-8 flex justify-center gap-2.5">
          {/* `next` carries the intended destination through sign-in. */}
          <ButtonLink href={`/account?next=${encodeURIComponent(pathname)}`}>
            Sign in or register
          </ButtonLink>
          <ButtonLink href="/shop" variant="secondary">
            Keep shopping
          </ButtonLink>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
