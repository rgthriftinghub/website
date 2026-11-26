"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { MediaImage as Image } from "@/components/ui/media-image";
import { createAdminCategory, createAdminSubcategory, listAdminBrands, listAdminCategories } from "@/lib/api/catalog";
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
  const [categoryName, setCategoryName] = useState("");
  const [categoryDescription, setCategoryDescription] = useState("");
  const [subcategoryParent, setSubcategoryParent] = useState("");
  const [subcategoryName, setSubcategoryName] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
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

  const slugify = (value: string) => value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  async function addCategory(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setError(null); setNotice("");
    try {
      await createAdminCategory({ name: categoryName.trim(), slug: slugify(categoryName), description: categoryDescription.trim() || undefined, sort_order: categories?.length ?? 0 });
      setCategoryName(""); setCategoryDescription(""); setNotice("Category added.");
      setCategories(await listAdminCategories());
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not add category."); }
    finally { setSaving(false); }
  }
  async function addSubcategory(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setError(null); setNotice("");
    try {
      await createAdminSubcategory({ category_id: subcategoryParent, name: subcategoryName.trim(), slug: slugify(subcategoryName) });
      setSubcategoryName(""); setNotice("Subcategory added."); setCategories(await listAdminCategories());
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not add subcategory."); }
    finally { setSaving(false); }
  }
  async function addCommonCategories() {
    setSaving(true); setError(null); setNotice("");
    const starter = [
      ["Men", ["Shirts", "T-shirts", "Jeans", "Trousers", "Jackets", "Hoodies", "Footwear", "Accessories"]],
      ["Women", ["Tops", "Dresses", "Jeans", "Trousers", "Abayas", "Skirts", "Footwear", "Accessories"]],
      ["Kids", ["Tops", "Bottoms", "Dresses", "Footwear"]],
      ["Unisex", ["T-shirts", "Hoodies", "Jackets", "Accessories"]],
      ["Accessories", ["Bags", "Belts", "Hats", "Jewellery"]],
    ] as const;
    try {
      let rows = await listAdminCategories();
      for (const [name, subcategoryNames] of starter) {
        let category = rows.find((row) => row.slug === slugify(name));
        if (!category) {
          await createAdminCategory({ name, slug: slugify(name), sort_order: rows.length });
          rows = await listAdminCategories();
          category = rows.find((row) => row.slug === slugify(name));
        }
        if (!category) continue;
        for (const subName of subcategoryNames) {
          if (category.subcategories.some((sub) => sub.slug === slugify(subName))) continue;
          await createAdminSubcategory({ category_id: category.id, name: subName, slug: slugify(subName) });
        }
        rows = await listAdminCategories();
      }
      setCategories(rows); setNotice("Common Men, Women, Kids, Unisex and Accessories categories are ready.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create the common categories."); }
    finally { setSaving(false); }
  }

  return (
    <>
      <header>
        <p className="eyebrow">Catalogue</p>
        <h1 className="mt-2 text-3xl">{copy.title}</h1>
        <p className="mt-2.5 max-w-2xl text-sm text-ink-muted">{copy.blurb}</p>
        {view === "categories" ? <p className="mt-2 text-xs text-stone">Add a category here, then choose it while adding a product.</p> : null}
      </header>

      {error ? <p className="mt-6 text-sm text-danger">{error}</p> : null}
      {loading && !error ? (
        <p className="mt-6 text-sm text-stone" role="status">
          Loading…
        </p>
      ) : null}

      {view === "categories" ? <div className="mt-7 grid gap-5 lg:grid-cols-2">
        <section className="flex flex-col items-start justify-center gap-3 border border-line bg-gold-wash p-5 lg:col-span-2 sm:flex-row sm:items-center sm:justify-between">
          <div><h2 className="font-display text-xl">Set up common clothing categories</h2><p className="mt-1 text-sm text-ink-muted">Creates Men, Women, Kids, Unisex and Accessories with useful clothing subcategories. Existing categories are kept.</p></div>
          <button type="button" disabled={saving} onClick={() => void addCommonCategories()} className="shrink-0 bg-ink px-5 py-3 text-xs font-semibold uppercase tracking-wider text-paper disabled:opacity-50">{saving ? "Setting up…" : "Add common categories"}</button>
        </section>
        <form onSubmit={addCategory} className="space-y-3 border border-line bg-paper p-5">
          <h2 className="font-display text-xl">Add a category</h2>
          <p className="text-xs text-ink-muted">Examples: Men, Women, Kids, Accessories. The URL slug is generated from the name.</p>
          <label className="block text-sm">Category name<input required maxLength={120} value={categoryName} onChange={(e) => setCategoryName(e.target.value)} placeholder="e.g. Men" className="mt-1 block h-11 w-full border border-line px-3" /></label>
          <label className="block text-sm">Description (optional)<input maxLength={500} value={categoryDescription} onChange={(e) => setCategoryDescription(e.target.value)} className="mt-1 block h-11 w-full border border-line px-3" /></label>
          <button disabled={saving} className="bg-ink px-5 py-3 text-xs font-semibold uppercase tracking-wider text-paper disabled:opacity-50">{saving ? "Saving…" : "Add category"}</button>
        </form>
        <form onSubmit={addSubcategory} className="space-y-3 border border-line bg-paper p-5">
          <h2 className="font-display text-xl">Add a subcategory</h2>
          <p className="text-xs text-ink-muted">Examples: Shirts, Jeans, Dresses, Shoes. Choose the parent category first.</p>
          <label className="block text-sm">Parent category<select required value={subcategoryParent} onChange={(e) => setSubcategoryParent(e.target.value)} className="mt-1 block h-11 w-full border border-line bg-white px-3"><option value="">Choose category</option>{(categories ?? []).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
          <label className="block text-sm">Subcategory name<input required maxLength={120} value={subcategoryName} onChange={(e) => setSubcategoryName(e.target.value)} placeholder="e.g. Jeans" className="mt-1 block h-11 w-full border border-line px-3" /></label>
          <button disabled={saving || !subcategoryParent} className="bg-ink px-5 py-3 text-xs font-semibold uppercase tracking-wider text-paper disabled:opacity-50">{saving ? "Saving…" : "Add subcategory"}</button>
        </form>
      </div> : null}
      {notice ? <p role="status" className="mt-4 text-sm text-green-800">{notice}</p> : null}

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
