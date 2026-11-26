import type { Metadata } from "next";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminActivity } from "@/components/admin/admin-people";

export const metadata: Metadata = {
  title: "Activity log | RG Thrifting Hub Admin",
  robots: { index: false, follow: false },
};

export default function Page() {
  return (
    <AdminGate>
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.16em] text-stone">Operations</p>
        <h1 className="mt-1 font-serif text-2xl text-ink">Activity log</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">Append-only record of consequential admin actions.</p>
      </header>
      <AdminActivity />
    </AdminGate>
  );
}