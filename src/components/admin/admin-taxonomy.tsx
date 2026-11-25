"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { MediaImage as Image } from "@/components/ui/media-image";
import { listAdminBrands, listAdminCategories } from "@/lib/api/catalog";
import type { Brand, CategoryDetail } from "@/lib/api/types";

type View = "categories" | "brands";

const COPY: Record<View, { title: string; blurb: string; endpoint: string }> = {
  categories: {
    title: "Categories",
    blurb:
      "Categories and their subcategories. Subcategory slugs are unique within a parent, so “men/jeans” and “women/jeans” can coexist.",
    endpoint: "/api/v1/admin/categories",
  },
  brands: {
    title: "Brands",
    blurb: "Brands available to products. Deactivating one hides it from the storefront without unlinking its products.",
    endpoint: "/api/v1/admin/brands",
  },
};

export function AdminTaxonomy({ view }: { view: View }) {
  const [categories, setCategories] = useState<CategoryDetail[] | null>(null);
  const [brands, setBrands] = useState<Brand[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const copy = COPY[view];

  useEffect(() => {
    const load = view === "categories" ? listAdminCategories() : listAdminBrands();
    load
      .then((result) => {
        if (view === "categories") setCategories(result as CategoryDetail[]);
        else setBrands(result as Brand[]);
      })
      .catch(() => setError(`Could not load ${view}.`));
  }, [view]);

  const loading = view === "categories" ? categories === null : brands === null;

  return (
    <>
      <header>
        <p className="eyebrow">Catalogue</p>
        <h1 className="mt-2 text-3xl">{copy.title}</h1>
        <p className="mt-2.5 max-w-2xl text-sm text-ink-muted">{copy.blurb}</p>
        <p className="mt-2 text-xs text-stone">
          Create, update and deactivate through{" "}
          <code className="text-ink-muted">{copy.endpoint}</code> (ADMIN or STAFF session required).
        </p>
      </header>

      {error ? <p className="mt-6 text-sm text-danger">{error}</p> : null}
      {loading && !error ? (
        <p className="mt-6 text-sm text-stone" role="status">
          Loading…
        </p>
      ) : null}

      {view === "categories" && categories ? (
        <div className="mt-7 space-y-4">
          {categories.map((category) => (
            <section key={category.id} className="border border-line bg-paper">
              <div className="flex flex-wrap items-center gap-4 border-b border-line p-5">
                {category.image_url ? (
                  <div className="relative h-14 w-20 shrink-0 overflow-hidden bg-paper-alt">
                    <Image
                      src={category.image_url}
                      alt=""
                      fill
                      sizes="80px"
                      className="object-cover"
                    />
                  </div>
                ) : null}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2.5">
                    <h2 className="font-display text-xl">{category.name}</h2>
                    {category.is_active ? (
                      <Badge tone="outline">Active</Badge>
                    ) : (
                      <Badge tone="soldout">Inactive</Badge>
                    )}
                  </div>
                  <p className="mt-0.5 font-mono text-[11px] text-stone">/{category.slug}</p>
                  {category.description ? (
                    <p className="mt-1.5 text-sm text-ink-muted">{category.description}</p>
                  ) : null}
                </div>
                <Link
                  href={`/categories/${category.slug}`}
                  className="text-xs font-semibold uppercase tracking-[0.12em] text-gold-deep hover:text-ink"
                >
                  View
                </Link>
              </div>

              {category.subcategories.length > 0 ? (
                <ul className="divide-y divide-line">
                  {category.subcategories.map((sub) => (
                    <li key={sub.id} className="flex items-center justify-between gap-4 px-5 py-3">
                      <div className="min-w-0">
                        <p className="text-sm text-ink">{sub.name}</p>
                        <p className="font-mono text-[11px] text-stone">/{sub.slug}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        <span className="text-xs text-stone">Order {sub.sort_order}</span>
                        {sub.is_active ? null : <Badge tone="soldout">Inactive</Badge>}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="px-5 py-3.5 text-sm text-stone">No subcategories yet.</p>
              )}
            </section>
          ))}
        </div>
      ) : null}

      {view === "brands" && brands ? (
        <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {brands.map((brand) => (
            <section key={brand.id} className="border border-line bg-paper p-5">
              <div className="flex items-start gap-4">
                {brand.logo_url ? (
                  <div className="relative size-14 shrink-0 border border-line">
                    <Image
                      src={brand.logo_url}
                      alt=""
                      fill
                      sizes="56px"
                      className="object-contain p-1"
                    />
                  </div>
                ) : null}
                <div className="min-w-0">
                  <h2 className="font-display text-lg">{brand.name}</h2>
                  <p className="font-mono text-[11px] text-stone">/{brand.slug}</p>
                </div>
              </div>
              {brand.description ? (
                <p className="mt-3 text-sm text-ink-muted">{brand.description}</p>
              ) : null}
              <div className="mt-4 flex items-center justify-between">
                {brand.is_active ? (
                  <Badge tone="outline">Active</Badge>
                ) : (
                  <Badge tone="soldout">Inactive</Badge>
                )}
                <Link
                  href={`/brands/${brand.slug}`}
                  className="text-xs font-semibold uppercase tracking-[0.12em] text-gold-deep hover:text-ink"
                >
                  View
                </Link>
              </div>
            </section>
          ))}
        </div>
      ) : null}
    </>
  );
}
