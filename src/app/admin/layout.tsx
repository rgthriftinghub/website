import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { AdminGate } from "@/components/admin/admin-gate";
import { Logo } from "@/components/brand/logo";

export const metadata: Metadata = {
  title: "Admin",
  // The admin area must never be indexed.
  robots: { index: false, follow: false },
};

const NAV = [
  { label: "Overview", href: "/admin" },
  { label: "Orders", href: "/admin/orders" },
  { label: "Payments", href: "/admin/payments" },
  { label: "Products", href: "/admin/products" },
  { label: "Inventory", href: "/admin/inventory" },
  { label: "Sales", href: "/admin/sales" },
  { label: "Coupons", href: "/admin/coupons" },
  { label: "Bulk", href: "/admin/bulk" },
  { label: "Customers", href: "/admin/customers" },
  { label: "Analytics", href: "/admin/analytics/sales" },
  { label: "Reports", href: "/admin/reports" },
  { label: "Import", href: "/admin/import" },
  { label: "Alerts", href: "/admin/notifications" },
  { label: "Activity", href: "/admin/activity" },
  { label: "Staff", href: "/admin/staff" },
  { label: "Store content", href: "/admin/content" },
  { label: "Categories", href: "/admin/categories" },
  { label: "Brands", href: "/admin/brands" },
];

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-paper-alt">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-20 max-w-7xl items-center gap-5 px-4 sm:px-6 lg:px-8">
          <Link href="/admin" aria-label="Admin home" className="shrink-0">
            <Logo height={58} priority />
          </Link>
          <span className="hidden text-[11px] font-semibold uppercase tracking-[0.14em] text-gold-deep sm:inline">
            Admin
          </span>

          <nav aria-label="Admin" className="no-scrollbar ml-auto flex gap-5 overflow-x-auto">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="nav-link whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted hover:text-ink"
              >
                {item.label}
              </Link>
            ))}
            <Link
              href="/"
              className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.12em] text-stone hover:text-ink"
            >
              View store
            </Link>
          </nav>
        </div>
      </header>

      {/* Server-side data still enforces roles; this guards the UI shell. */}
      <AdminGate>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-9 sm:px-6 lg:px-8">{children}</main>
      </AdminGate>
    </div>
  );
}
