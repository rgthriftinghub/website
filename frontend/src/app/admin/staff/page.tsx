import type { Metadata } from "next";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminStaff } from "@/components/admin/admin-people";

export const metadata: Metadata = {
  title: "Staff | RG Thrifting Hub Admin",
  robots: { index: false, follow: false },
};

export default function Page() {
  return (
    <AdminGate>
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.16em] text-stone">Settings</p>
        <h1 className="mt-1 font-serif text-2xl text-ink">Staff permissions</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">Admins hold everything. Staff hold only what is explicitly granted, and new accounts start read-only.</p>
      </header>
      <AdminStaff />
    </AdminGate>
  );
}