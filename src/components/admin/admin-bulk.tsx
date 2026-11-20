"use client";

/**
 * Bulk product management: attributes, prices, and stock.
 *
 * Price changes are previewed before they are applied — the preview comes from the
 * backend and shows the exact before/after for every affected product. Stock changes
 * require a reason, because every one writes an inventory movement that someone will
 * later have to reconcile.
 */

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  applyPrices,
  bulkUpdateProducts,
  bulkUpdateStock,
  getSelectionVariants,
  previewPrices,
} from "@/lib/api/admin";
import { listAdminCategories, listProducts } from "@/lib/api/catalog";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Category, PricePreview, ProductListItem } from "@/lib/api/types";

const FIELD =
  "w-full border border-line bg-paper px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-gold";
const LABEL = "text-[11px] font-semibold uppercase tracking-[0.12em] text-stone";
const PANEL = "border border-line bg-surface p-5";
const HEAD = "text-[11px] font-semibold uppercase tracking-[0.14em] text-ink";

type Tab = "attributes" | "prices" | "stock";

type VariantRow = {
  variant_id: string;
  sku: string;
  size: string | null;
  waist: number | null;
  product_name: string;
  quantity: number;
};

export function AdminBulk() {
  const [tab, setTab] = useState<Tab>("attributes");
  const [products, setProducts] = useState<ProductListItem[] | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listProducts({ search: search || undefined, page_size: 100 })
      .then((page) => {
        if (!cancelled) setProducts(page.items);
      })
      .catch(() => {
        if (!cancelled) setProducts([]);
      });
    return () => {
      cancelled = true;
    };
  }, [search, reloadKey]);

  useEffect(() => {
    listAdminCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  const ids = useMemo(() => Array.from(selected), [selected]);

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function done(detail: string) {
    setMessage(detail);
    setError(null);
    setSelected(new Set());
    setReloadKey((key) => key + 1);
  }

  return (
    <div className="space-y-5">
      <div className="flex gap-1 border border-line bg-surface p-1">
        {(
          [
            ["attributes", "Attributes"],
            ["prices", "Prices"],
            ["stock", "Stock"],
          ] as [Tab, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            className={cn(
              "px-3 py-1.5 text-xs font-medium transition-colors",
              tab === value ? "bg-ink text-paper" : "text-ink-muted hover:text-ink"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {message ? (
        <p className="border border-success/30 bg-success/8 px-4 py-3 text-sm text-success">
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {error}
        </p>
      ) : null}

      <section className={PANEL}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className={HEAD}>1 · Choose products</h2>
          <span className="text-xs text-ink-muted">{selected.size} selected</span>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <input
            defaultValue={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search products"
            aria-label="Search products"
            className={cn(FIELD, "max-w-xs")}
          />
          <Button
            variant="secondary"
            onClick={() => setSelected(new Set((products ?? []).map((p) => p.id)))}
          >
            Select all shown
          </Button>
          <Button variant="ghost" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </div>

        {products === null ? (
          <p className="py-8 text-center text-sm text-stone">Loading products…</p>
        ) : (
          <div className="mt-4 max-h-72 overflow-auto border border-line">
            <table className="w-full text-sm">
              <tbody>
                {products.map((product) => (
                  <tr key={product.id} className="border-b border-line/60 last:border-0">
                    <td className="w-10 px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(product.id)}
                        onChange={() => toggle(product.id)}
                        aria-label={`Select ${product.name}`}
                        className="accent-gold"
                      />
                    </td>
                    <td className="px-2 py-2 text-ink">{product.name}</td>
                    <td className="px-2 py-2 font-mono text-xs text-stone">{product.sku}</td>
                    <td className="px-2 py-2 text-right tabular-nums text-ink-muted">
                      {formatPrice(product.regular_price)}
                    </td>
                    <td className="px-3 py-2 text-right text-xs text-stone">
                      {product.total_stock} in stock
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {tab === "attributes" ? (
        <AttributesPanel
          ids={ids}
          categories={categories}
          onDone={done}
          onError={setError}
        />
      ) : null}
      {tab === "prices" ? <PricesPanel ids={ids} onDone={done} onError={setError} /> : null}
      {tab === "stock" ? <StockPanel ids={ids} onDone={done} onError={setError} /> : null}
    </div>
  );
}

function AttributesPanel({
  ids,
  categories,
  onDone,
  onError,
}: {
  ids: string[];
  categories: Category[];
  onDone: (detail: string) => void;
  onError: (message: string) => void;
}) {
  const [categoryId, setCategoryId] = useState("");
  const [subcategoryId, setSubcategoryId] = useState("");
  const [flags, setFlags] = useState<Record<string, boolean | undefined>>({});
  const [busy, setBusy] = useState(false);

  const subcategories =
    categories.find((category) => category.id === categoryId)?.subcategories ?? [];

  function setFlag(key: string, value: string) {
    setFlags((current) => ({
      ...current,
      [key]: value === "" ? undefined : value === "true",
    }));
  }

  async function apply() {
    setBusy(true);
    try {
      const result = await bulkUpdateProducts({
        product_ids: ids,
        is_active: flags.is_active,
        is_featured: flags.is_featured,
        is_new_arrival: flags.is_new_arrival,
        category_id: categoryId || undefined,
        subcategory_id: subcategoryId || undefined,
      });
      onDone(result.detail);
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not apply changes.");
    } finally {
      setBusy(false);
    }
  }

  const nothingToDo =
    !categoryId &&
    !subcategoryId &&
    flags.is_active === undefined &&
    flags.is_featured === undefined &&
    flags.is_new_arrival === undefined;

  return (
    <section className={PANEL}>
      <h2 className={HEAD}>2 · Set attributes</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        {[
          ["is_active", "Status"],
          ["is_featured", "Featured"],
          ["is_new_arrival", "New arrival"],
        ].map(([key, label]) => (
          <label key={key} className="flex flex-col gap-1.5">
            <span className={LABEL}>{label}</span>
            <select
              value={flags[key] === undefined ? "" : String(flags[key])}
              onChange={(event) => setFlag(key, event.target.value)}
              className={FIELD}
            >
              <option value="">Leave unchanged</option>
              <option value="true">{key === "is_active" ? "Active" : "Yes"}</option>
              <option value="false">{key === "is_active" ? "Inactive" : "No"}</option>
            </select>
          </label>
        ))}

        <label className="flex flex-col gap-1.5">
          <span className={LABEL}>Category</span>
          <select
            value={categoryId}
            onChange={(event) => {
              setCategoryId(event.target.value);
              setSubcategoryId("");
            }}
            className={FIELD}
          >
            <option value="">Leave unchanged</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>

        {categoryId ? (
          <label className="flex flex-col gap-1.5">
            <span className={LABEL}>Subcategory</span>
            <select
              value={subcategoryId}
              onChange={(event) => setSubcategoryId(event.target.value)}
              className={FIELD}
            >
              <option value="">Leave unchanged</option>
              {subcategories.map((subcategory) => (
                <option key={subcategory.id} value={subcategory.id}>
                  {subcategory.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      <p className="mt-4 text-[11px] text-stone">
        A subcategory must belong to the category it is applied with; the backend
        rejects a mismatch rather than filing the product wrongly.
      </p>

      <Button
        className="mt-4"
        disabled={busy || ids.length === 0 || nothingToDo}
        onClick={() => {
          if (
            window.confirm(
              `Apply these changes to ${ids.length} product${ids.length === 1 ? "" : "s"}?`
            )
          ) {
            void apply();
          }
        }}
      >
        {busy ? "Applying…" : `Apply to ${ids.length} products`}
      </Button>
    </section>
  );
}

function PricesPanel({
  ids,
  onDone,
  onError,
}: {
  ids: string[];
  onDone: (detail: string) => void;
  onError: (message: string) => void;
}) {
  const [mode, setMode] = useState("decrease_percent");
  const [value, setValue] = useState("10");
  const [field, setField] = useState<"regular_price" | "sale_price">("sale_price");
  const [preview, setPreview] = useState<PricePreview | null>(null);
  const [busy, setBusy] = useState(false);

  const body = {
    product_ids: ids,
    mode,
    value: String(Number(value) || 0),
    field,
  };

  async function runPreview() {
    setBusy(true);
    try {
      setPreview(await previewPrices(body));
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not preview.");
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    setBusy(true);
    try {
      const result = await applyPrices(body);
      setPreview(null);
      onDone(result.detail);
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not apply prices.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={PANEL}>
      <h2 className={HEAD}>2 · Change prices</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <label className="flex flex-col gap-1.5">
          <span className={LABEL}>Field</span>
          <select
            value={field}
            onChange={(event) => setField(event.target.value as typeof field)}
            className={FIELD}
          >
            <option value="sale_price">Sale price</option>
            <option value="regular_price">Regular price</option>
          </select>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className={LABEL}>Operation</span>
          <select value={mode} onChange={(event) => setMode(event.target.value)} className={FIELD}>
            <option value="decrease_percent">Decrease by %</option>
            <option value="increase_percent">Increase by %</option>
            <option value="decrease_amount">Decrease by amount</option>
            <option value="increase_amount">Increase by amount</option>
            <option value="set">Set to</option>
          </select>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className={LABEL}>Value</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            className={FIELD}
          />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="secondary" disabled={busy || ids.length === 0} onClick={runPreview}>
          {busy ? "Working…" : "Preview"}
        </Button>
        {preview && preview.affected > 0 ? (
          <Button
            disabled={busy}
            onClick={() => {
              if (
                window.confirm(
                  `Apply this price change to ${preview.affected} product${
                    preview.affected === 1 ? "" : "s"
                  }? This cannot be undone automatically.`
                )
              ) {
                void apply();
              }
            }}
          >
            Apply to {preview.affected}
          </Button>
        ) : null}
      </div>

      {preview ? (
        preview.affected === 0 ? (
          <p className="mt-4 text-sm text-ink-muted">
            No product in the selection would change. A sale price must end up below the
            regular price, and only &ldquo;set&rdquo; can create one where none exists.
          </p>
        ) : (
          <div className="mt-4">
            <div className="grid grid-cols-2 gap-px border border-line bg-line sm:grid-cols-4">
              {[
                ["Affected", String(preview.affected)],
                ["Before", formatPrice(preview.total_before)],
                ["After", formatPrice(preview.total_after)],
                ["Change", formatPrice(preview.total_change)],
              ].map(([label, text]) => (
                <div key={label} className="bg-surface px-3 py-2.5">
                  <p className="text-[10px] uppercase tracking-[0.12em] text-stone">{label}</p>
                  <p className="mt-0.5 font-serif text-lg text-ink">{text}</p>
                </div>
              ))}
            </div>
            <div className="mt-3 max-h-64 overflow-auto border border-line">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-paper-alt">
                  <tr className="text-left text-[11px] uppercase tracking-[0.12em] text-stone">
                    <th className="px-3 py-2 font-medium">Product</th>
                    <th className="px-3 py-2 text-right font-medium">Before</th>
                    <th className="px-3 py-2 text-right font-medium">After</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row) => (
                    <tr key={row.product_id} className="border-b border-line/60">
                      <td className="px-3 py-2 text-ink">{row.name}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-stone line-through">
                        {formatPrice(row.current_price)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums font-medium text-ink">
                        {formatPrice(row.new_price)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      ) : null}
    </section>
  );
}

function StockPanel({
  ids,
  onDone,
  onError,
}: {
  ids: string[];
  onDone: (detail: string) => void;
  onError: (message: string) => void;
}) {
  const [variants, setVariants] = useState<VariantRow[] | null>(null);
  const [mode, setMode] = useState<"add" | "remove" | "set">("add");
  const [quantity, setQuantity] = useState("5");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // No synchronous clear when the selection empties: the render below already
    // treats an empty selection as nothing to show, and setting state inline here
    // would trigger a cascading render.
    if (ids.length === 0) return;

    let cancelled = false;
    getSelectionVariants(ids)
      .then((rows) => {
        if (!cancelled) setVariants(rows);
      })
      .catch(() => {
        if (!cancelled) setVariants([]);
      });
    return () => {
      cancelled = true;
    };
  }, [ids]);

  // Derived, so a cleared selection shows nothing without an extra state write.
  const rows = ids.length === 0 ? [] : (variants ?? []);

  async function apply() {
    if (rows.length === 0) return;
    setBusy(true);
    try {
      const result = await bulkUpdateStock({
        adjustments: rows.map((variant) => ({
          variant_id: variant.variant_id,
          mode,
          quantity: Number(quantity) || 0,
        })),
        reason: reason.trim(),
      });
      onDone(result.detail);
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not adjust stock.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={PANEL}>
      <h2 className={HEAD}>2 · Adjust stock</h2>
      <p className="mt-1 text-xs text-ink-muted">
        Applies to every variant of the selected products. Each change writes an
        inventory movement with before and after quantities.
      </p>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <label className="flex flex-col gap-1.5">
          <span className={LABEL}>Operation</span>
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value as typeof mode)}
            className={FIELD}
          >
            <option value="add">Add stock</option>
            <option value="remove">Remove stock</option>
            <option value="set">Set stock to</option>
          </select>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className={LABEL}>Quantity</span>
          <input
            type="number"
            min="0"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            className={FIELD}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className={LABEL}>Reason (required)</span>
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Received new shipment"
            className={FIELD}
          />
        </label>
      </div>

      {rows.length > 0 ? (
        <div className="mt-4 max-h-56 overflow-auto border border-line">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-paper-alt">
              <tr className="text-left text-[11px] uppercase tracking-[0.12em] text-stone">
                <th className="px-3 py-2 font-medium">Product</th>
                <th className="px-3 py-2 font-medium">SKU</th>
                <th className="px-3 py-2 text-right font-medium">Now</th>
                <th className="px-3 py-2 text-right font-medium">After</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((variant) => {
                const amount = Number(quantity) || 0;
                const next =
                  mode === "add"
                    ? variant.quantity + amount
                    : mode === "remove"
                      ? Math.max(variant.quantity - amount, 0)
                      : amount;
                return (
                  <tr key={variant.variant_id} className="border-b border-line/60">
                    <td className="px-3 py-2 text-ink">{variant.product_name}</td>
                    <td className="px-3 py-2 font-mono text-xs text-stone">{variant.sku}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-stone">
                      {variant.quantity}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums font-medium text-ink">
                      {next}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      <Button
        className="mt-4"
        disabled={busy || rows.length === 0 || reason.trim().length < 3}
        onClick={() => {
          if (
            window.confirm(
              `Adjust stock on ${rows.length} variants? This is recorded in the inventory history.`
            )
          ) {
            void apply();
          }
        }}
      >
        {busy ? "Applying…" : `Adjust ${rows.length} variants`}
      </Button>
    </section>
  );
}
