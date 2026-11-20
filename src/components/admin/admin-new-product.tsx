"use client";

import Link from "next/link";
import { ArrowLeft, Terminal } from "lucide-react";
import { useEffect, useState } from "react";

import { listAdminBrands, listAdminCategories } from "@/lib/api/catalog";
import type { Brand, CategoryDetail } from "@/lib/api/types";

/**
 * Product creation reference.
 *
 * The write API is complete and tested; the full authoring form (image upload,
 * variant matrix builder) is a later phase. Until then this page documents the
 * exact contract and surfaces the real category/brand ids an operator needs,
 * rather than pretending to be a form that does not submit.
 */
export function AdminNewProduct() {
  const [categories, setCategories] = useState<CategoryDetail[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);

  useEffect(() => {
    listAdminCategories().then(setCategories).catch(() => setCategories([]));
    listAdminBrands().then(setBrands).catch(() => setBrands([]));
  }, []);

  const exampleCategory = categories[0];
  const exampleSubcategory = exampleCategory?.subcategories[0];
  const exampleBrand = brands[0];

  const payload = {
    name: "Straight Leg Jeans in Deep Indigo",
    slug: "straight-leg-jeans-deep-indigo",
    sku: "RG-MJ-2001",
    short_description: "Rigid 13oz denim with a clean straight leg.",
    seo_title: "Straight Leg Jeans | RG Thrifting Hub",
    meta_description: "Shop these deep indigo straight leg jeans from RG Thrifting Hub.",
    description: "Longer copy shown on the product page.",
    category_id: exampleCategory?.id ?? "<category uuid>",
    subcategory_id: exampleSubcategory?.id ?? "<subcategory uuid>",
    brand_id: exampleBrand?.id ?? "<brand uuid>",
    regular_price: "5200.00",
    sale_price: "3900.00",
    condition: "GOOD",
    gender: "MEN",
    product_type: "JEANS",
    color: "Indigo",
    fabric: "Denim",
    is_featured: true,
    is_new_arrival: true,
    images: [
      { image_url: "/demo/products/example-1.png", alt_text: "Front", is_primary: true },
      { image_url: "/demo/products/example-2.png", alt_text: "Back", sort_order: 1 },
    ],
    variants: [
      { sku: "RG-MJ-2001-W30", waist: 30, quantity: 5 },
      { sku: "RG-MJ-2001-W32", waist: 32, quantity: 8 },
      { sku: "RG-MJ-2001-W34", waist: 34, quantity: 0 },
    ],
  };

  return (
    <>
      <Link
        href="/admin/products"
        className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted hover:text-ink"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        Back to products
      </Link>

      <header className="mt-5">
        <p className="eyebrow">Catalogue</p>
        <h1 className="mt-2 text-3xl">New product</h1>
        <p className="mt-2.5 max-w-2xl text-sm text-ink-muted">
          Products are created through <code className="text-ink">POST /api/v1/admin/products</code>,
          which requires an ADMIN or STAFF session. Each variant carries its own stock, so a sold-out
          waist disables only that waist on the storefront.
        </p>
      </header>

      <section className="mt-8 border border-line bg-paper p-6">
        <h2 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
          <Terminal className="size-3.5 text-gold-deep" aria-hidden />
          Request body
        </h2>
        <pre className="mt-4 overflow-x-auto bg-ink p-5 text-xs leading-relaxed text-paper/90">
          <code>{JSON.stringify(payload, null, 2)}</code>
        </pre>
      </section>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <ReferenceList
          title="Category ids"
          rows={categories.flatMap((category) => [
            { label: category.name, value: category.id },
            ...category.subcategories.map((sub) => ({
              label: `— ${sub.name}`,
              value: sub.id,
            })),
          ])}
        />
        <ReferenceList
          title="Brand ids"
          rows={brands.map((brand) => ({ label: brand.name, value: brand.id }))}
        />
      </div>

      <section className="mt-4 border border-line bg-gold-wash p-6">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
          Field rules
        </h2>
        <ul className="mt-3 space-y-1.5 text-sm text-ink-muted">
          <li>
            <strong className="text-ink">slug</strong> — lowercase, hyphen separated, unique across
            products.
          </li>
          <li>
            <strong className="text-ink">sku</strong> — unique across products; variant SKUs are
            unique too. <strong className="text-ink">barcode</strong> is optional, since thrift
            pieces often have none.
          </li>
          <li>
            <strong className="text-ink">sale_price</strong> — must be lower than{" "}
            <strong className="text-ink">regular_price</strong>. Both are exact decimals, never
            floats.
          </li>
          <li>
            <strong className="text-ink">condition</strong> — PREMIUM_PLUS, PREMIUM, EXCELLENT or GOOD. Legacy imports using NEW, EXPORT_QUALITY or THRIFT are normalized to the matching grade.
          </li>
          <li>
            <strong className="text-ink">variants</strong> — each needs at least one of size, waist
            or colour, and its own <strong className="text-ink">quantity</strong>.
          </li>
          <li>
            <strong className="text-ink">images</strong> — at most one may be{" "}
            <strong className="text-ink">is_primary</strong>; the first is promoted automatically.
          </li>
        </ul>
      </section>
    </>
  );
}

function ReferenceList({
  title,
  rows,
}: {
  title: string;
  rows: { label: string; value: string }[];
}) {
  return (
    <section className="border border-line bg-paper p-5">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">{title}</h2>
      {rows.length === 0 ? (
        <p className="mt-3 text-sm text-stone">Nothing yet.</p>
      ) : (
        <dl className="mt-3 space-y-1.5">
          {rows.map((row) => (
            <div key={row.value} className="flex items-baseline justify-between gap-3">
              <dt className="text-sm text-ink-muted">{row.label}</dt>
              <dd className="font-mono text-[11px] text-stone">{row.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
