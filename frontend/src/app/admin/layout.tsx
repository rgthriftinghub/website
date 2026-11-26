import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminNavigation } from "@/components/admin/admin-navigation";
import { Logo } from "@/components/brand/logo";

export const metadata: Metadata = {
  title: "Admin",
  // The admin area must never be indexed.
  robots: { index: false, follow: false },
};

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-paper-alt">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-20 max-w-7xl items-center gap-5 px-4 sm:px-6 lg:px-8">
          <Link href="/admin" aria-label="Admin home" className="shrink-0">
            <Logo height={58} priority />
          </Link>
          <span className="hidden text-[11px] font-semibold uppercase tracking-[0.14em] text-gold-deep sm:inline">
            Admin
          </span>

          <AdminNavigation />
        </div>
      </header>

      {/* Server-side data still enforces roles; this guards the UI shell. */}
      <AdminGate>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-9 sm:px-6 lg:px-8">{children}</main>
      </AdminGate>
    </div>
  );
}
