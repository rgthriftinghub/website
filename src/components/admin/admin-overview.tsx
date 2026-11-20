"use client";

import Link from "next/link";
import { AlertTriangle, Boxes, Shapes, Tags } from "lucide-react";
import { useEffect, useState } from "react";

import { listAdminBrands, listAdminCategories, listAdminProducts } from "@/lib/api/catalog";
import type { Brand, CategoryDetail, ProductAdmin } from "@/lib/api/types";

interface Summary {
  products: number;
  activeProducts: number;
  categories: number;
  subcategories: number;
  brands: number;
  outOfStockVariants: number;
  lowStockVariants: number;
  sample: ProductAdmin[];
}

function summarise(
  products: ProductAdmin[],
  total: number,
  categories: CategoryDetail[],
  brands: Brand[]
): Summary {
  const variants = products.flatMap((product) => product.variants);
  return {
    products: total,
    activeProducts: products.filter((product) => product.is_active).length,
    categories: categories.length,
    subcategories: categories.reduce((sum, category) => sum + category.subcategories.length, 0),
    brands: brands.length,
    outOfStockVariants: variants.filter((variant) => variant.is_active && !variant.in_stock).length,
    lowStockVariants: variants.filter((variant) => variant.is_low_stock).length,
    sample: products.slice(0, 5),
  };
}

export function AdminOverview() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      // page_size is capped at 100 by the API; this overview is a snapshot of
      // the first page, not a full-catalogue report.
      listAdminProducts({ page_size: 100 }),
      listAdminCategories(),
      listAdminBrands(),
    ])
      .then(([productPage, categories, brands]) =>
        setSummary(summarise(productPage.items, productPage.total, categories, brands))
      )
      .catch(() => setError("Could not load catalogue data."));
  }, []);

  if (error) {
    return <p className="text-sm text-danger">{error}</p>;
  }

  if (!summary) {
    return (
      <p className="text-sm text-stone" role="status">
        Loading catalogue…
      </p>
    );
  }

  const cards = [
    { label: "Products", value: summary.products, href: "/admin/products", icon: Boxes },
    { label: "Categories", value: summary.categories, href: "/admin/categories", icon: Shapes },
    { label: "Brands", value: summary.brands, href: "/admin/brands", icon: Tags },
    {
      label: "Sold-out variants",
      value: summary.outOfStockVariants,
      href: "/admin/products",
      icon: AlertTriangle,
    },
  ];

  return (
    <>
      <header>
        <p className="eyebrow">Admin</p>
        <h1 className="mt-2 text-3xl">Catalogue overview</h1>
        <p className="mt-2.5 max-w-2xl text-sm text-ink-muted">
          Read-only foundation for this phase. Product, category and brand writes are available
          through the API; the full management dashboard arrives in a later phase.
        </p>
      </header>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map(({ label, value, href, icon: Icon }) => (
          <Link
            key={label}
            href={href}
            className="border border-line bg-paper p-5 transition-colors hover:border-gold"
          >
            <Icon className="size-4 text-gold-deep" aria-hidden />
            <p className="mt-3 font-display text-3xl">{value}</p>
            <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
              {label}
            </p>
          </Link>
        ))}
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div className="border border-line bg-paper p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
            Subcategories
          </p>
          <p className="mt-2 font-display text-2xl">{summary.subcategories}</p>
        </div>
        <div className="border border-line bg-paper p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
            Low-stock variants
          </p>
          <p className="mt-2 font-display text-2xl">{summary.lowStockVariants}</p>
        </div>
      </div>

      <section className="mt-10">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
          Recently added
        </h2>
        <ul className="mt-3 divide-y divide-line border border-line bg-paper">
          {summary.sample.map((product) => (
            <li key={product.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
              <div className="min-w-0">
                <p className="truncate text-sm text-ink">{product.name}</p>
                <p className="text-xs text-stone">
                  {product.sku} · {product.variants.length} variant
                  {product.variants.length === 1 ? "" : "s"}
                </p>
              </div>
              <span className="shrink-0 text-xs text-ink-muted">
                {product.is_active ? "Active" : "Inactive"}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
