import type { Metadata } from "next";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminBulk } from "@/components/admin/admin-bulk";

export const metadata: Metadata = {
  title: "Bulk management | RG Thrifting Hub Admin",
  robots: { index: false, follow: false },
};

export default function Page() {
  return (
    <AdminGate>
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.16em] text-stone">Operations</p>
        <h1 className="mt-1 font-serif text-2xl text-ink">Bulk management</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">Update attributes, prices, or stock across many products at once. Price changes preview first.</p>
      </header>
      <AdminBulk />
    </AdminGate>
  );
}