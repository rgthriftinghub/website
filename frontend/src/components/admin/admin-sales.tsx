"use client";

/**
 * Sale campaign management.
 *
 * Status is reported by the backend (`is_live` / `is_scheduled`), never inferred
 * from dates here — the server owns the activation rule, so the list can't drift
 * out of step with what customers actually see.
 */

import { useEffect, useState } from "react";

import { Button, ButtonLink } from "@/components/ui/button";
import { deleteSale, listSales, setSaleActive } from "@/lib/api/admin";
import { formatDateTime, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Sale } from "@/lib/api/types";

const FILTERS = [
  { value: "", label: "All" },
  { value: "live", label: "Live" },
  { value: "scheduled", label: "Scheduled" },
  { value: "expired", label: "Expired" },
  { value: "inactive", label: "Inactive" },
];

export function saleStatusLabel(sale: Sale): { label: string; tone: string } {
  if (!sale.is_active) return { label: "Inactive", tone: "bg-line text-ink-muted" };
  if (sale.is_live) return { label: "Live", tone: "bg-success/12 text-success" };
  if (sale.is_scheduled) return { label: "Scheduled", tone: "bg-gold-wash text-gold-deep" };
  return { label: "Ended", tone: "bg-line text-ink-muted" };
}

export function discountLabel(sale: Sale): string {
  const value = Number(sale.discount_value);
  if (sale.discount_type === "PERCENTAGE") return `${value}% off`;
  if (sale.discount_type === "FIXED_AMOUNT") return `${formatPrice(value)} off`;
  return `Set to ${formatPrice(value)}`;
}

export function AdminSales() {
  const [sales, setSales] = useState<Sale[] | null>(null);
  const [filter, setFilter] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listSales({ status: filter || undefined, page_size: 50 })
      .then((page) => {
        if (!cancelled) setSales(page.items);
      })
      .catch((cause) => {
        if (!cancelled) {
          setSales([]);
          setError(cause instanceof Error ? cause.message : "Could not load sales.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [filter, reloadKey]);

  async function act(id: string, action: () => Promise<unknown>) {
    setBusyId(id);
    setError(null);
    try {
      await action();
      setReloadKey((key) => key + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That action failed.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1 border border-line bg-surface p-1">
          {FILTERS.map((entry) => (
            <button
              key={entry.value}
              type="button"
              onClick={() => setFilter(entry.value)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium transition-colors",
                filter === entry.value
                  ? "bg-ink text-paper"
                  : "text-ink-muted hover:bg-paper-alt hover:text-ink"
              )}
            >
              {entry.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <ButtonLink href="/admin/sales/flash" variant="secondary">
            New flash sale
          </ButtonLink>
          <ButtonLink href="/admin/sales/new">New campaign</ButtonLink>
        </div>
      </div>

      {error ? (
        <p role="alert" className="border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {error}
        </p>
      ) : null}

      {sales === null ? (
        <p className="py-10 text-center text-sm text-stone">Loading campaigns…</p>
      ) : sales.length === 0 ? (
        <p className="border border-line bg-surface py-12 text-center text-sm text-stone">
          No campaigns yet.
        </p>
      ) : (
        <div className="overflow-x-auto border border-line bg-surface">
          <table className="w-full min-w-[60rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-[11px] uppercase tracking-[0.12em] text-stone">
                <th className="px-4 py-3 font-medium">Campaign</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Discount</th>
                <th className="px-4 py-3 font-medium">Applies to</th>
                <th className="px-4 py-3 text-right font-medium">Priority</th>
                <th className="px-4 py-3 text-right font-medium">Products</th>
                <th className="px-4 py-3 font-medium">Window</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sales.map((sale) => {
                const status = saleStatusLabel(sale);
                return (
                  <tr key={sale.id} className="border-b border-line/70 align-top">
                    <td className="px-4 py-3">
                      <p className="font-medium text-ink">{sale.name}</p>
                      {sale.badge_text ? (
                        <p className="text-xs text-stone">Badge: {sale.badge_text}</p>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">
                      {sale.sale_type.charAt(0) + sale.sale_type.slice(1).toLowerCase()}
                    </td>
                    <td className="px-4 py-3 text-ink">{discountLabel(sale)}</td>
                    <td className="px-4 py-3">
                      <ul className="space-y-0.5 text-xs text-ink-muted">
                        {sale.targets.map((target) => (
                          <li key={target.id}>{target.label ?? target.target_type}</li>
                        ))}
                      </ul>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">
                      {sale.priority}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-muted">
                      {sale.affected_product_count}
                    </td>
                    <td className="px-4 py-3 text-xs text-stone">
                      {formatDateTime(sale.starts_at)}
                      <br />
                      {sale.ends_at ? formatDateTime(sale.ends_at) : "No end date"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-sm px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
                          status.tone
                        )}
                      >
                        {status.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="secondary"
                          disabled={busyId === sale.id}
                          onClick={() =>
                            act(sale.id, () => setSaleActive(sale.id, !sale.is_active))
                          }
                        >
                          {sale.is_active ? "Deactivate" : "Activate"}
                        </Button>
                        <Button
                          variant="ghost"
                          disabled={busyId === sale.id}
                          onClick={() => {
                            if (
                              window.confirm(
                                `Delete "${sale.name}"? Prices return to normal immediately. Past orders are unaffected.`
                              )
                            ) {
                              void act(sale.id, () => deleteSale(sale.id));
                            }
                          }}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="border border-line bg-paper-alt p-4">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
          How overlapping campaigns resolve
        </h2>
        <ol className="mt-2 list-decimal space-y-0.5 pl-5 text-xs leading-relaxed text-ink-muted">
          <li>Highest <strong>priority</strong> wins.</li>
          <li>Then the narrower target: product &gt; brand &gt; subcategory &gt; category &gt; store.</li>
          <li>Then the larger discount.</li>
          <li>Then the later start date.</li>
        </ol>
        <p className="mt-2 text-xs text-stone">
          Campaigns never stack, and a hand-set sale price still wins when it is cheaper.
        </p>
      </div>
    </div>
  );
}
