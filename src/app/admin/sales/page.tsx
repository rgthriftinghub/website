import type { Metadata } from "next";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminSales } from "@/components/admin/admin-sales";

export const metadata: Metadata = {
  title: "Sales | RG Thrifting Hub Admin",
  robots: { index: false, follow: false },
};

export default function Page() {
  return (
    <AdminGate>
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.16em] text-stone">Merchandising</p>
        <h1 className="mt-1 font-serif text-2xl text-ink">Sale campaigns</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">Campaigns are rules, not catalogue edits: ending one restores original prices instantly, and past orders are never affected.</p>
      </header>
      <AdminSales />
    </AdminGate>
  );
}