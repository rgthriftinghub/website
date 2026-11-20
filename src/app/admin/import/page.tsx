import type { Metadata } from "next";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminImport } from "@/components/admin/admin-import";

export const metadata: Metadata = {
  title: "Import | RG Thrifting Hub Admin",
  robots: { index: false, follow: false },
};

export default function Page() {
  return (
    <AdminGate>
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.16em] text-stone">Operations</p>
        <h1 className="mt-1 font-serif text-2xl text-ink">Product import</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">Upload a CSV or Excel file. Nothing is written to the catalogue until you review the preview and confirm.</p>
      </header>
      <AdminImport />
    </AdminGate>
  );
}