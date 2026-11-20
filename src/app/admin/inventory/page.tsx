import type { Metadata } from "next";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminStock } from "@/components/admin/admin-stock";

export const metadata: Metadata = {
  title: "Inventory | RG Thrifting Hub Admin",
  robots: { index: false, follow: false },
};

export default function Page() {
  return (
    <AdminGate>
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.16em] text-stone">Operations</p>
        <h1 className="mt-1 font-serif text-2xl text-ink">Inventory</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">
          Stock per variant, compared against each variant&apos;s own threshold. Every
          adjustment requires a reason and is recorded in the movement history.
        </p>
      </header>
      <AdminStock />
    </AdminGate>
  );
}