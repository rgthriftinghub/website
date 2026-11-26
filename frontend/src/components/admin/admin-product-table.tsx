"use client";

import { MediaImage as Image } from "@/components/ui/media-image";
import Link from "next/link";
import { Plus, Search, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { useAdminUser } from "@/components/admin/admin-gate";
import { ButtonLink } from "@/components/ui/button";
import { deleteAdminProduct, listAdminProducts } from "@/lib/api/catalog";
import type { Page, ProductAdmin } from "@/lib/api/types";
import { conditionLabel, formatPrice } from "@/lib/format";

const PAGE_SIZE = 20;

export function AdminProductTable() {
  const [data, setData] = useState<Page<ProductAdmin> | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [applied, setApplied] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [showInactive, setShowInactive] = useState(false);
  const user = useAdminUser();

  useEffect(() => {
    let cancelled = false;
    listAdminProducts({
      page,
      page_size: PAGE_SIZE,
      include_inactive: showInactive,
      ...(applied ? { search: applied } : {}),
    })
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load products.");
      });
    return () => {
      cancelled = true;
    };
  }, [page, applied, reloadKey, showInactive]);

  async function removeProduct(product: ProductAdmin) {
    if (!window.confirm(`Remove “${product.name}” from the storefront? Its order and stock history will be retained.`)) return;
    setBusyId(product.id);
    setError(null);
    try {
      await deleteAdminProduct(product.id);
      setReloadKey((key) => key + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not remove this product.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Catalogue</p>
          <h1 className="mt-2 text-3xl">Products</h1>
          <p className="mt-2 text-sm text-ink-muted">
            {data ? `${data.total} product${data.total === 1 ? "" : "s"}${showInactive ? ", including removed products" : ""}.` : "Loading…"}
          </p>
        </div>
        <ButtonLink href="/admin/products/new" size="sm">
          <Plus className="size-3.5" aria-hidden />
          New product
        </ButtonLink>
      </header>

      <form
        className="mt-6 flex max-w-md gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
          setApplied(search.trim());
        }}
      >
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-stone"
            aria-hidden
          />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search name, SKU or brand"
            aria-label="Search products"
            className="h-10 w-full border border-line bg-paper pl-9 pr-3 text-sm outline-none focus:border-gold"
          />
        </div>
        <button
          type="submit"
          className="h-10 border border-line-strong px-4 text-xs font-semibold uppercase tracking-[0.12em] text-ink transition-colors hover:border-ink"
        >
          Search
        </button>
      </form>

      <label className="mt-3 inline-flex items-center gap-2 text-xs text-ink-muted">
        <input type="checkbox" checked={showInactive} onChange={(event) => { setPage(1); setShowInactive(event.target.checked); }} />
        Show removed products
      </label>

      {error ? <p className="mt-6 text-sm text-danger">{error}</p> : null}

      {data ? (
        <>
          {/* Horizontal scroll keeps the table usable on narrow screens without
              collapsing the columns an operator needs side by side. */}
          <div className="mt-6 overflow-x-auto border border-line bg-paper">
            <table className="w-full min-w-[46rem] text-left text-sm">
              <thead className="border-b border-line bg-paper-alt">
                <tr className="text-[10px] uppercase tracking-[0.12em] text-ink-muted">
                  <th scope="col" className="px-4 py-3 font-semibold">Product</th>
                  <th scope="col" className="px-4 py-3 font-semibold">SKU</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Price</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Stock</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Condition</th>
                  <th scope="col" className="px-4 py-3 font-semibold">State</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.items.map((product) => {
                  const image = product.images.find((i) => i.is_primary) ?? product.images[0];
                  const soldOutVariants = product.variants.filter(
                    (variant) => variant.is_active && !variant.in_stock
                  ).length;
                  return (
                    <tr key={product.id} className="align-middle">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="relative size-11 shrink-0 overflow-hidden bg-paper-alt">
                            {image ? (
                              <Image
                                src={image.image_url}
                                alt=""
                                fill
                                sizes="44px"
                                className="object-cover"
                              />
                            ) : null}
                          </div>
                          <div className="min-w-0">
                            <Link
                              href={`/shop/${product.slug}`}
                              className="block truncate text-ink hover:text-gold-deep"
                            >
                              {product.name}
                            </Link>
                            <p className="truncate text-xs text-stone">
                              {product.brand?.name ?? "No brand"} · {product.category.name}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-muted">{product.sku}</td>
                      <td className="px-4 py-3">
                        <span className="text-ink">{formatPrice(product.effective_price)}</span>
                        {product.is_on_sale ? (
                          <span className="ml-1.5 text-xs text-stone line-through">
                            {formatPrice(product.regular_price)}
                          </span>
                        ) : null}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-ink">{product.total_stock}</span>
                        <span className="ml-1 text-xs text-stone">
                          across {product.variants.length}
                        </span>
                        {soldOutVariants > 0 ? (
                          <p className="mt-0.5 text-[11px] text-gold-deep">
                            {soldOutVariants} size{soldOutVariants === 1 ? "" : "s"} sold out
                          </p>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 text-xs text-ink-muted">
                        {conditionLabel(product.condition)}
                      </td>
                      <td className="px-4 py-3">
                        {product.is_active ? (
                          <Badge tone="outline">Active</Badge>
                        ) : (
                          <Badge tone="soldout">Inactive</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <Link href={`/admin/products/${product.id}/edit`} className="text-xs font-semibold uppercase tracking-wider text-ink underline decoration-gold underline-offset-4">Edit</Link>
                          {product.is_active && user?.role === "ADMIN" ? (
                            <button type="button" onClick={() => void removeProduct(product)} disabled={busyId === product.id}
                              className="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-danger hover:underline disabled:opacity-50"
                              aria-label={`Delete ${product.name}`}>
                              <Trash2 className="size-3.5" aria-hidden />{busyId === product.id ? "Removing…" : "Delete"}
                            </button>
                          ) : <span className="text-xs text-stone">Removed</span>}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {data.items.length === 0 ? (
            <p className="mt-6 text-sm text-ink-muted">No products match that search.</p>
          ) : null}

          {data.total_pages > 1 ? (
            <div className="mt-6 flex items-center justify-between">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                className="h-10 border border-line-strong px-4 text-xs uppercase tracking-[0.12em] disabled:opacity-40"
              >
                Previous
              </button>
              <p className="text-xs text-ink-muted">
                Page {data.page} of {data.total_pages}
              </p>
              <button
                type="button"
                disabled={page >= data.total_pages}
                onClick={() => setPage((current) => current + 1)}
                className="h-10 border border-line-strong px-4 text-xs uppercase tracking-[0.12em] disabled:opacity-40"
              >
                Next
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </>
  );
}
