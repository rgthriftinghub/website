"use client";

/**
 * Reports and exports.
 *
 * Downloads are plain links, not fetches, so the browser streams the file straight
 * to disk with the session cookie attached — a large order export never has to be
 * held in JavaScript memory first.
 */

import { useState } from "react";

import { DateFilter } from "@/components/admin/date-filter";
import { exportUrl } from "@/lib/api/admin";
import type { DateRangeQuery } from "@/lib/api/types";

const DATASETS = [
  {
    key: "sales",
    label: "Sales by period",
    detail: "Orders, gross and net sales bucketed by day, week, month, or year.",
    dated: true,
  },
  {
    key: "orders",
    label: "Orders",
    detail: "One row per order with totals, payment, status, and tracking number.",
    dated: true,
  },
  {
    key: "order_items",
    label: "Order line items",
    detail: "One row per line, for reconciling exactly what sold.",
    dated: true,
  },
  {
    key: "products",
    label: "Products and variants",
    detail: "One row per variant: pricing, stock, category, brand, and status.",
    dated: false,
  },
  {
    key: "inventory",
    label: "Current stock",
    detail: "Live stock levels against each variant's own threshold.",
    dated: false,
  },
  {
    key: "inventory_history",
    label: "Stock movements",
    detail: "Every adjustment with before and after quantities.",
    dated: true,
  },
  {
    key: "customers",
    label: "Customers",
    detail: "Order counts, lifetime spend, and segment. No passwords.",
    dated: false,
  },
];

const GRANULARITIES = ["day", "week", "month", "year"];

export function AdminReports() {
  const [range, setRange] = useState<DateRangeQuery>({ preset: "last_30_days" });
  const [granularity, setGranularity] = useState("day");
  const [includeInactive, setIncludeInactive] = useState(false);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <DateFilter value={range} onChange={setRange} />
        <label className="flex items-center gap-2 text-xs text-ink-muted">
          Bucket
          <select
            value={granularity}
            onChange={(event) => setGranularity(event.target.value)}
            className="border border-line bg-surface px-2 py-1.5 text-xs text-ink outline-none focus:border-gold"
          >
            {GRANULARITIES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs text-ink-muted">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(event) => setIncludeInactive(event.target.checked)}
            className="accent-gold"
          />
          Include inactive products
        </label>
      </div>

      <div className="grid gap-px overflow-hidden border border-line bg-line sm:grid-cols-2">
        {DATASETS.map((dataset) => {
          const query = {
            ...(dataset.dated ? range : {}),
            granularity,
            include_inactive: includeInactive || undefined,
          };
          return (
            <div key={dataset.key} className="flex flex-col gap-3 bg-surface p-5">
              <div>
                <h2 className="font-serif text-lg text-ink">{dataset.label}</h2>
                <p className="mt-1 text-sm leading-relaxed text-ink-muted">
                  {dataset.detail}
                </p>
                {dataset.dated ? (
                  <p className="mt-1 text-[11px] text-stone">
                    Uses the selected date range.
                  </p>
                ) : null}
              </div>
              <div className="mt-auto flex gap-2">
                <a
                  href={exportUrl(dataset.key, "csv", query)}
                  className="inline-flex items-center border border-ink bg-ink px-3.5 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-paper transition-colors hover:bg-ink/90"
                >
                  CSV
                </a>
                <a
                  href={exportUrl(dataset.key, "xlsx", query)}
                  className="inline-flex items-center border border-line-strong px-3.5 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink transition-colors hover:border-ink"
                >
                  Excel
                </a>
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-[11px] leading-relaxed text-stone">
        CSV exports stream and have no row limit. Excel exports are capped at 20,000
        rows; when the cap is reached the workbook says so on its final row — use CSV
        for larger datasets.
      </p>
    </div>
  );
}
