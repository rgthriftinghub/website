import type { Metadata } from "next";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminDashboard } from "@/components/admin/admin-dashboard";

export const metadata: Metadata = {
  title: "Dashboard | RG Thrifting Hub Admin",
  robots: { index: false, follow: false },
};

export default function AdminHomePage() {
  return (
    <AdminGate>
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.16em] text-stone">Overview</p>
        <h1 className="mt-1 font-serif text-2xl text-ink">Business dashboard</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">
          Trading figures, stock health, and customer mix. Every number is aggregated
          by the database for the selected period.
        </p>
      </header>
      <AdminDashboard />
    </AdminGate>
  );
}
