import type { Metadata } from "next";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminCustomers } from "@/components/admin/admin-people";

export const metadata: Metadata = {
  title: "Customers | RG Thrifting Hub Admin",
  robots: { index: false, follow: false },
};

export default function Page() {
  return (
    <AdminGate>
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.16em] text-stone">Operations</p>
        <h1 className="mt-1 font-serif text-2xl text-ink">Customers</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">Order history, lifetime spend, segment, and private staff notes.</p>
      </header>
      <AdminCustomers />
    </AdminGate>
  );
}