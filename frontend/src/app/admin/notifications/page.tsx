import type { Metadata } from "next";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminNotifications } from "@/components/admin/admin-people";

export const metadata: Metadata = {
  title: "Notifications | RG Thrifting Hub Admin",
  robots: { index: false, follow: false },
};

export default function Page() {
  return (
    <AdminGate>
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.16em] text-stone">Operations</p>
        <h1 className="mt-1 font-serif text-2xl text-ink">Notifications</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">New orders, stock alerts, payment issues, and return requests.</p>
      </header>
      <AdminNotifications />
    </AdminGate>
  );
}