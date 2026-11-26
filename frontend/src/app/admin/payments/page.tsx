import type { Metadata } from "next";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminPayments } from "@/components/admin/admin-payments";

export const metadata: Metadata = {
  title: "Payments · RG Thrifting Hub Admin",
  robots: { index: false, follow: false },
};

export default function AdminPaymentsPage() {
  return (
    <AdminGate>
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.16em] text-stone">Operations</p>
        <h1 className="mt-1 font-serif text-2xl text-ink">Payments</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Verify bank transfers, record cash collected on delivery, and review the
          audit trail. Gateway payments settle through verified callbacks and cannot
          be edited by hand.
        </p>
      </header>
      <AdminPayments />
    </AdminGate>
  );
}
