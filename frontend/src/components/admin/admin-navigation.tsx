"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getAdminAccess, type AdminAccess } from "@/lib/api/admin";
import type { Permission } from "@/lib/api/types";

const NAV: {
  label: string;
  href: string;
  permissions?: Permission[];
  adminOnly?: boolean;
}[] = [
  { label: "Overview", href: "/admin", permissions: ["REPORTS_VIEW"] },
  { label: "Orders", href: "/admin/orders", permissions: ["ORDER_VIEW"] },
  { label: "Payments", href: "/admin/payments", permissions: ["PAYMENT_VIEW"] },
  { label: "Products", href: "/admin/products", permissions: ["PRODUCT_VIEW"] },
  { label: "Inventory", href: "/admin/inventory", permissions: ["INVENTORY_VIEW"] },
  { label: "Sales", href: "/admin/sales", permissions: ["SALES_VIEW"] },
  { label: "Coupons", href: "/admin/coupons", permissions: ["SALES_VIEW"] },
  { label: "Bulk", href: "/admin/bulk", permissions: ["PRODUCT_UPDATE", "INVENTORY_UPDATE"] },
  { label: "Customers", href: "/admin/customers", permissions: ["CUSTOMER_VIEW"] },
  { label: "Analytics", href: "/admin/analytics/sales", permissions: ["REPORTS_VIEW"] },
  { label: "Reports", href: "/admin/reports", permissions: ["REPORTS_VIEW"] },
  { label: "Import", href: "/admin/import", permissions: ["PRODUCT_CREATE"] },
  { label: "Alerts", href: "/admin/notifications", permissions: ["INVENTORY_VIEW"] },
  { label: "Activity", href: "/admin/activity", permissions: ["REPORTS_VIEW"] },
  { label: "Staff", href: "/admin/staff", adminOnly: true },
  { label: "Store content", href: "/admin/content", permissions: ["SETTINGS_MANAGE"] },
  { label: "Categories", href: "/admin/categories", permissions: ["PRODUCT_VIEW"] },
  { label: "Brands", href: "/admin/brands", permissions: ["PRODUCT_VIEW"] },
];

export function AdminNavigation() {
  const [access, setAccess] = useState<AdminAccess | null>(null);

  useEffect(() => {
    getAdminAccess().then(setAccess).catch(() => setAccess(null));
  }, []);

  const visibleLinks = access
    ? NAV.filter((item) => {
        if (access.role === "ADMIN") return true;
        if (item.adminOnly || !item.permissions) return false;
        return item.permissions.some((permission) => access.permissions.includes(permission));
      })
    : [];

  return (
    <nav aria-label="Admin" className="no-scrollbar ml-auto flex gap-5 overflow-x-auto">
      {visibleLinks.map((item) => (
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
  );
}
