"use client";

/**
 * The business control panel.
 *
 * One request per date-range change — the backend assembles every KPI, chart, and
 * table in a fixed small number of queries, so this component never fans out into
 * a dozen calls.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

import { RankedBars, RevenueChart, SplitDonut, StatusBar } from "@/components/admin/charts";
import { DateFilter, KpiTile } from "@/components/admin/date-filter";
import { getDashboard } from "@/lib/api/admin";
import { formatPrice } from "@/lib/format";
import type { DashboardSummary, DateRangeQuery } from "@/lib/api/types";

const STATUS_TONES: Record<string, string> = {
  PENDING: "bg-gold-wash",
  PROCESSING: "bg-gold",
  PACKED: "bg-line-strong",
  DISPATCHED: "bg-ink-muted",
  DELIVERED: "bg-success",
  CANCELLED: "bg-danger",
  RETURNED: "bg-danger/60",
  EXCHANGE: "bg-danger/40",
};

function compact(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${Math.round(value / 1_000)}k`;
  return String(Math.round(value));
}

export function AdminDashboard() {
  const [query, setQuery] = useState<DateRangeQuery>({ preset: "last_30_days" });
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDashboard(query)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Could not load the dashboard.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [query]);

  if (error) {
    return (
      <p role="alert" className="border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
        {error}
      </p>
    );
  }

  if (!data) {
    return (
      <p className="grid h-64 place-items-center text-sm text-stone" role="status">
        Loading dashboard…
      </p>
    );
  }

  const statuses = data.order_statuses;
  const todayOrders = Object.values(data.today.orders).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-8">
      <DateFilter value={query} onChange={setQuery} rangeLabel={data.range.label} />

      {/* Today at a glance */}
      <section>
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-stone">
          Today
        </h2>
        <div className="grid grid-cols-2 gap-px overflow-hidden border border-line bg-line sm:grid-cols-4 lg:grid-cols-8">
          <KpiTile label="Orders today" value={String(todayOrders)} />
          <KpiTile label="Sales today" value={formatPrice(data.today.sales)} />
          <KpiTile label="Pending" value={String(statuses.PENDING ?? 0)} tone="warning" />
          <KpiTile label="Processing" value={String(statuses.PROCESSING ?? 0)} />
          <KpiTile label="Delivered" value={String(statuses.DELIVERED ?? 0)} tone="good" />
          <KpiTile label="Cancelled" value={String(statuses.CANCELLED ?? 0)} tone="critical" />
          <KpiTile label="Returned" value={String(statuses.RETURNED ?? 0)} tone="critical" />
          <KpiTile
            label="Stock value"
            value={formatPrice(data.inventory.inventory_value)}
            hint={`${data.inventory.total_units} units`}
          />
        </div>
      </section>

      {/* Period figures */}
      <section>
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-stone">
          Sales
        </h2>
        <div className="grid grid-cols-2 gap-px overflow-hidden border border-line bg-line sm:grid-cols-4 lg:grid-cols-7">
          <KpiTile label="This week" value={formatPrice(data.period_sales.week)} />
          <KpiTile label="This month" value={formatPrice(data.period_sales.month)} />
          <KpiTile label="This year" value={formatPrice(data.period_sales.year)} />
          <KpiTile
            label="Net sales"
            value={formatPrice(data.selected.net_sales)}
            hint={data.range.label}
            change={data.selected.net_sales_change_percent}
          />
          <KpiTile
            label="Orders"
            value={String(data.selected.order_count)}
            change={data.selected.order_count_change_percent}
          />
          <KpiTile
            label="Avg order"
            value={formatPrice(data.selected.average_order_value)}
          />
          <KpiTile label="Items sold" value={String(data.selected.items_sold)} />
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="border border-line bg-surface p-5 lg:col-span-2">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Net sales
            </h2>
            <span className="text-xs text-stone">{data.range.label}</span>
          </div>
          <div className="mt-4">
            <RevenueChart points={data.timeseries} />
          </div>
        </section>

        <section className="border border-line bg-surface p-5">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
            Customers
          </h2>
          <div className="mt-4">
            <SplitDonut
              centerLabel="total"
              centerValue={compact(data.customers.total)}
              segments={[
                { label: "New", value: data.customers.new, color: "var(--gold)" },
                { label: "Repeat", value: data.customers.repeat, color: "var(--ink-muted)" },
                { label: "Loyal", value: data.customers.loyal, color: "var(--ink)" },
              ]}
            />
          </div>
          <p className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-stone">
            Segments use lifetime non-cancelled orders: new is under{" "}
            {data.customers.segment_rule.REPEAT_MIN}, repeat is{" "}
            {data.customers.segment_rule.REPEAT_MIN}–
            {data.customers.segment_rule.LOYAL_MIN - 1}, loyal is{" "}
            {data.customers.segment_rule.LOYAL_MIN}+.
          </p>
        </section>
      </div>

      <section className="border border-line bg-surface p-5">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
          Orders by status
        </h2>
        <div className="mt-4">
          <StatusBar
            segments={Object.entries(statuses).map(([label, value]) => ({
              label: label.charAt(0) + label.slice(1).toLowerCase(),
              value,
              tone: STATUS_TONES[label] ?? "bg-line-strong",
            }))}
          />
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="border border-line bg-surface p-5">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
            Top selling
          </h2>
          <div className="mt-4">
            <RankedBars rows={data.top_products} valueKey="units_sold"
                        formatValue={(v) => `${v} sold`} />
          </div>
        </section>

        <section className="border border-line bg-surface p-5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Slowest moving
            </h2>
            <Link
              href="/admin/analytics/products?sort=units_asc"
              className="text-[11px] text-ink-muted underline decoration-gold/50 underline-offset-4"
            >
              All products
            </Link>
          </div>
          <ul className="mt-4 space-y-2 text-sm">
            {data.low_selling_products.map((product) => (
              <li key={product.id} className="flex items-baseline justify-between gap-3">
                <span className="min-w-0 truncate text-ink">{product.name}</span>
                <span className="shrink-0 tabular-nums text-stone">
                  {product.units_sold} sold · {product.stock} in stock
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="border border-line bg-surface p-5">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
            Revenue by category
          </h2>
          <div className="mt-4">
            <RankedBars rows={data.category_sales} />
          </div>
        </section>

        <section className="border border-line bg-surface p-5">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
            Revenue by brand
          </h2>
          <div className="mt-4">
            <RankedBars rows={data.brand_sales} />
          </div>
        </section>
      </div>

      {/* Inventory attention */}
      <section className="grid grid-cols-2 gap-px overflow-hidden border border-line bg-line sm:grid-cols-3 lg:grid-cols-6">
        <KpiTile label="Active products" value={String(data.inventory.active_products)} />
        <KpiTile label="Variants" value={String(data.inventory.total_variants)} />
        <KpiTile label="Units on hand" value={String(data.inventory.total_units)} />
        <KpiTile
          label="Low stock"
          value={String(data.inventory.low_stock_variants)}
          tone={data.inventory.low_stock_variants > 0 ? "warning" : "default"}
        />
        <KpiTile
          label="Out of stock"
          value={String(data.inventory.out_of_stock_variants)}
          tone={data.inventory.out_of_stock_variants > 0 ? "critical" : "default"}
        />
        <KpiTile label="Discounts given" value={formatPrice(data.selected.discounts)} />
      </section>

      <p className="text-[11px] text-stone">
        All figures aggregated by the database. Cancelled orders are excluded from
        revenue but counted in the status breakdown.
      </p>
    </div>
  );
}
