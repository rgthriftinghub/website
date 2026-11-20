"use client";

/**
 * Analytics screens. Each fetches one pre-aggregated payload and renders it.
 *
 * The low-selling view sorts ascending and deliberately includes products with zero
 * sales — no arbitrary "low selling" threshold is applied anywhere.
 */

import { useEffect, useState } from "react";

import { RankedBars, RevenueChart, SplitDonut, StatusBar } from "@/components/admin/charts";
import { DateFilter, KpiTile } from "@/components/admin/date-filter";
import {
  getCustomerAnalytics,
  getInventoryAlerts,
  getInventoryAnalytics,
  getOrderAnalytics,
  getProductAnalytics,
  getSalesAnalytics,
  scanStockAlerts,
} from "@/lib/api/admin";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  CustomerAnalytics,
  DateRangeQuery,
  InventorySummary,
  OrderAnalytics,
  ProductPerformanceRow,
  SalesAnalytics,
  StockAlertRow,
} from "@/lib/api/types";
import { Button } from "@/components/ui/button";

const PANEL = "border border-line bg-surface p-5";
const HEAD = "text-[11px] font-semibold uppercase tracking-[0.14em] text-ink";
const TH = "px-4 py-3 text-left text-[11px] uppercase tracking-[0.12em] font-medium text-stone";

function Loading({ label }: { label: string }) {
  return (
    <p className="grid h-48 place-items-center text-sm text-stone" role="status">
      {label}
    </p>
  );
}

// ------------------------------------------------------------------------ sales
export function SalesAnalyticsView() {
  const [range, setRange] = useState<DateRangeQuery>({ preset: "last_30_days" });
  const [granularity, setGranularity] = useState("day");
  const [brandSort, setBrandSort] = useState("revenue");
  const [data, setData] = useState<SalesAnalytics | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSalesAnalytics({ ...range, granularity, brand_sort: brandSort })
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [range, granularity, brandSort]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <DateFilter value={range} onChange={setRange} rangeLabel={data?.range.label} />
        <label className="flex items-center gap-2 text-xs text-ink-muted">
          Bucket
          <select
            value={granularity}
            onChange={(event) => setGranularity(event.target.value)}
            className="border border-line bg-surface px-2 py-1.5 text-xs text-ink outline-none focus:border-gold"
          >
            {["day", "week", "month", "year"].map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
      </div>

      {!data ? (
        <Loading label="Loading sales analytics…" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-px overflow-hidden border border-line bg-line sm:grid-cols-4 lg:grid-cols-7">
            <KpiTile label="Gross sales" value={formatPrice(data.totals.gross_sales)} />
            <KpiTile label="Discounts" value={formatPrice(data.totals.discounts)} />
            <KpiTile label="Delivery" value={formatPrice(data.totals.shipping_revenue)} />
            <KpiTile label="Net sales" value={formatPrice(data.totals.net_sales)} />
            <KpiTile label="Orders" value={String(data.totals.order_count)} />
            <KpiTile label="Items sold" value={String(data.totals.items_sold)} />
            <KpiTile label="Avg order" value={formatPrice(data.totals.average_order_value)} />
          </div>

          <section className={PANEL}>
            <h2 className={HEAD}>Net sales over time</h2>
            <div className="mt-4">
              <RevenueChart points={data.timeseries} height={240} />
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className={PANEL}>
              <h2 className={HEAD}>By category</h2>
              <div className="mt-4"><RankedBars rows={data.by_category} /></div>
            </section>
            <section className={PANEL}>
              <h2 className={HEAD}>By subcategory</h2>
              <div className="mt-4"><RankedBars rows={data.by_subcategory} /></div>
            </section>
          </div>

          <section className={PANEL}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className={HEAD}>By brand</h2>
              <div className="flex gap-1 border border-line p-1">
                {[
                  { value: "revenue", label: "Revenue" },
                  { value: "units", label: "Units" },
                  { value: "orders", label: "Orders" },
                ].map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setBrandSort(option.value)}
                    className={cn(
                      "px-2.5 py-1 text-xs font-medium transition-colors",
                      brandSort === option.value
                        ? "bg-ink text-paper"
                        : "text-ink-muted hover:text-ink"
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[36rem] text-sm">
                <thead>
                  <tr className="border-b border-line">
                    <th className={TH}>Brand</th>
                    <th className={cn(TH, "text-right")}>Orders</th>
                    <th className={cn(TH, "text-right")}>Units</th>
                    <th className={cn(TH, "text-right")}>Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_brand.map((row) => (
                    <tr key={row.id} className="border-b border-line/60">
                      <td className="px-4 py-2.5 text-ink">{row.name}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-ink-muted">{row.orders}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-ink-muted">{row.units_sold}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums font-medium text-ink">
                        {formatPrice(row.revenue)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

// --------------------------------------------------------------------- products
export function ProductAnalyticsView() {
  const [range, setRange] = useState<DateRangeQuery>({ preset: "last_30_days" });
  const [sort, setSort] = useState("units");
  const [rows, setRows] = useState<ProductPerformanceRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => {
    let cancelled = false;
    getProductAnalytics({ ...range, sort, page, page_size: 25 })
      .then((result) => {
        if (!cancelled) {
          setRows(result.items);
          setTotal(result.total);
        }
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      });
    return () => {
      cancelled = true;
    };
  }, [range, sort, page]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <DateFilter value={range} onChange={(next) => { setRange(next); setPage(1); }} />
        <div className="flex gap-1 border border-line bg-surface p-1">
          {[
            { value: "units", label: "Top selling" },
            { value: "units_asc", label: "Slowest moving" },
            { value: "revenue", label: "By revenue" },
            { value: "orders", label: "By orders" },
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => { setSort(option.value); setPage(1); }}
              className={cn(
                "px-2.5 py-1.5 text-xs font-medium transition-colors",
                sort === option.value ? "bg-ink text-paper" : "text-ink-muted hover:text-ink"
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {sort === "units_asc" ? (
        <p className="border-l-2 border-gold bg-gold-wash px-3 py-2 text-xs text-ink-muted">
          Products with no sales at all are included, which is the point — a plain
          sales aggregation would omit exactly the ones you need to see.
        </p>
      ) : null}

      {rows === null ? (
        <Loading label="Loading product performance…" />
      ) : (
        <div className="overflow-x-auto border border-line bg-surface">
          <table className="w-full min-w-[58rem] text-sm">
            <thead>
              <tr className="border-b border-line">
                <th className={TH}>Product</th>
                <th className={TH}>SKU</th>
                <th className={TH}>Brand</th>
                <th className={cn(TH, "text-right")}>Units</th>
                <th className={cn(TH, "text-right")}>Orders</th>
                <th className={cn(TH, "text-right")}>Revenue</th>
                <th className={cn(TH, "text-right")}>Avg sold at</th>
                <th className={cn(TH, "text-right")}>Stock</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-line/60">
                  <td className="px-4 py-2.5 text-ink">{row.name}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-stone">{row.sku}</td>
                  <td className="px-4 py-2.5 text-ink-muted">{row.brand_name ?? "—"}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-medium text-ink">
                    {row.units_sold}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-ink-muted">{row.orders}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-ink">
                    {formatPrice(row.revenue)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-ink-muted">
                    {row.units_sold > 0 ? formatPrice(row.average_selling_price) : "—"}
                  </td>
                  <td
                    className={cn(
                      "px-4 py-2.5 text-right tabular-nums",
                      row.stock === 0 ? "text-danger" : "text-ink-muted"
                    )}
                  >
                    {row.stock}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-line px-4 py-3 text-sm text-ink-muted">
            <span>{total} products</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={page * 25 >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------------- inventory
export function InventoryAnalyticsView() {
  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [low, setLow] = useState<StockAlertRow[]>([]);
  const [out, setOut] = useState<StockAlertRow[]>([]);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getInventoryAnalytics(),
      getInventoryAlerts(false, 1, 100),
      getInventoryAlerts(true, 1, 100),
    ])
      .then(([summaryResult, lowResult, outResult]) => {
        if (cancelled) return;
        setSummary(summaryResult);
        setLow(lowResult.items);
        setOut(outResult.items);
      })
      .catch(() => {
        if (!cancelled) setSummary(null);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  async function handleScan() {
    setBusy(true);
    try {
      const result = await scanStockAlerts();
      setScanResult(
        `Raised ${result.low_stock ?? 0} low-stock and ${result.out_of_stock ?? 0} out-of-stock alerts.`
      );
      setReloadKey((key) => key + 1);
    } catch {
      setScanResult("Could not run the scan.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      {summary ? (
        <div className="grid grid-cols-2 gap-px overflow-hidden border border-line bg-line sm:grid-cols-3 lg:grid-cols-6">
          <KpiTile label="Active products" value={String(summary.active_products)} />
          <KpiTile label="Variants" value={String(summary.total_variants)} />
          <KpiTile label="Units on hand" value={String(summary.total_units)} />
          <KpiTile
            label="Low stock"
            value={String(summary.low_stock_variants)}
            tone={summary.low_stock_variants ? "warning" : "default"}
          />
          <KpiTile
            label="Out of stock"
            value={String(summary.out_of_stock_variants)}
            tone={summary.out_of_stock_variants ? "critical" : "default"}
          />
          <KpiTile label="Stock value" value={formatPrice(summary.inventory_value)} />
        </div>
      ) : (
        <Loading label="Loading inventory…" />
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" disabled={busy} onClick={handleScan}>
          {busy ? "Scanning…" : "Re-scan stock alerts"}
        </Button>
        {scanResult ? <span className="text-xs text-ink-muted">{scanResult}</span> : null}
      </div>

      <AlertTable
        title="Out of stock"
        rows={out}
        tone="critical"
        empty="Nothing is out of stock."
      />
      <AlertTable
        title="Low stock"
        rows={low}
        tone="warning"
        empty="No variant is below its threshold."
      />

      <p className="text-[11px] leading-relaxed text-stone">
        Each variant is compared against its own threshold, not a global number — a
        staple and a one-off thrift piece do not warrant the same reorder point.
        Stock is valued at each product&apos;s effective selling price, excluding
        temporary campaign discounts.
      </p>
    </div>
  );
}

function AlertTable({
  title,
  rows,
  tone,
  empty,
}: {
  title: string;
  rows: StockAlertRow[];
  tone: "warning" | "critical";
  empty: string;
}) {
  return (
    <section className="border border-line bg-surface">
      <div className="flex items-baseline justify-between border-b border-line px-5 py-3.5">
        <h2 className={HEAD}>{title}</h2>
        <span className={cn("text-xs font-medium", tone === "critical" ? "text-danger" : "text-gold-deep")}>
          {rows.length}
        </span>
      </div>
      {rows.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-stone">{empty}</p>
      ) : (
        <div className="max-h-80 overflow-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <thead className="sticky top-0 bg-paper-alt">
              <tr>
                <th className={TH}>Product</th>
                <th className={TH}>Variant</th>
                <th className={TH}>SKU</th>
                <th className={cn(TH, "text-right")}>Stock</th>
                <th className={cn(TH, "text-right")}>Threshold</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.variant_id} className="border-b border-line/60">
                  <td className="px-4 py-2.5 text-ink">{row.product_name}</td>
                  <td className="px-4 py-2.5 text-ink-muted">
                    {row.waist !== null ? `Waist ${row.waist}` : row.size ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-stone">{row.sku}</td>
                  <td
                    className={cn(
                      "px-4 py-2.5 text-right tabular-nums font-medium",
                      row.quantity === 0 ? "text-danger" : "text-gold-deep"
                    )}
                  >
                    {row.quantity}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-stone">
                    {row.low_stock_threshold}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// -------------------------------------------------------------------- customers
export function CustomerAnalyticsView() {
  const [range, setRange] = useState<DateRangeQuery>({ preset: "last_30_days" });
  const [data, setData] = useState<CustomerAnalytics | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCustomerAnalytics(range)
      .then((result) => {
        if (!cancelled) setData(result as CustomerAnalytics);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [range]);

  return (
    <div className="space-y-6">
      <DateFilter value={range} onChange={setRange} />
      {!data ? (
        <Loading label="Loading customer analytics…" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-px overflow-hidden border border-line bg-line sm:grid-cols-3 lg:grid-cols-6">
            <KpiTile label="Total customers" value={String(data.total)} />
            <KpiTile label="New in period" value={String(data.new)} />
            <KpiTile label="Repeat" value={String(data.repeat)} />
            <KpiTile label="Loyal" value={String(data.loyal)} />
            <KpiTile label="Avg order" value={formatPrice(data.average_order_value)} />
            <KpiTile label="Revenue" value={formatPrice(data.total_revenue)} />
          </div>

          <section className="border border-line bg-surface p-5">
            <h2 className={HEAD}>Segments</h2>
            <div className="mt-4">
              <SplitDonut
                centerLabel="with orders"
                centerValue={String(data.with_orders)}
                segments={[
                  { label: "Repeat", value: data.repeat, color: "var(--gold)" },
                  { label: "Loyal", value: data.loyal, color: "var(--ink)" },
                  {
                    label: "New / one order",
                    value: Math.max(data.total - data.repeat - data.loyal, 0),
                    color: "var(--line-strong)",
                  },
                ]}
              />
            </div>
            <p className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-stone">
              Segmentation counts lifetime non-cancelled orders. New is fewer than{" "}
              {data.segment_rule.REPEAT_MIN}; repeat is {data.segment_rule.REPEAT_MIN}
              –{data.segment_rule.LOYAL_MIN - 1}; loyal is {data.segment_rule.LOYAL_MIN}
              {" "}or more.
            </p>
          </section>
        </>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------- orders
export function OrderAnalyticsView() {
  const [range, setRange] = useState<DateRangeQuery>({ preset: "last_30_days" });
  const [data, setData] = useState<OrderAnalytics | null>(null);

  useEffect(() => {
    let cancelled = false;
    getOrderAnalytics(range)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [range]);

  const tones: Record<string, string> = {
    PENDING: "bg-gold-wash",
    PROCESSING: "bg-gold",
    PACKED: "bg-line-strong",
    DISPATCHED: "bg-ink-muted",
    DELIVERED: "bg-success",
    CANCELLED: "bg-danger",
    RETURNED: "bg-danger/60",
    EXCHANGE: "bg-danger/40",
  };

  return (
    <div className="space-y-6">
      <DateFilter value={range} onChange={setRange} rangeLabel={data?.range.label} />
      {!data ? (
        <Loading label="Loading order analytics…" />
      ) : (
        <>
          <div className="grid grid-cols-3 gap-px overflow-hidden border border-line bg-line sm:grid-cols-5 lg:grid-cols-9">
            <KpiTile label="Total" value={String(data.total_orders)} />
            {Object.entries(data.order_statuses).map(([status, count]) => (
              <KpiTile
                key={status}
                label={status.charAt(0) + status.slice(1).toLowerCase()}
                value={String(count)}
                tone={
                  status === "DELIVERED"
                    ? "good"
                    : status === "CANCELLED" || status === "RETURNED"
                      ? "critical"
                      : "default"
                }
              />
            ))}
          </div>

          <section className="border border-line bg-surface p-5">
            <h2 className={HEAD}>Status mix</h2>
            <div className="mt-4">
              <StatusBar
                segments={Object.entries(data.order_statuses).map(([label, value]) => ({
                  label: label.charAt(0) + label.slice(1).toLowerCase(),
                  value,
                  tone: tones[label] ?? "bg-line-strong",
                }))}
              />
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="border border-line bg-surface p-5">
              <h2 className={HEAD}>Payment status</h2>
              <ul className="mt-4 space-y-2 text-sm">
                {Object.entries(data.payment_statuses)
                  .filter(([, count]) => count > 0)
                  .map(([status, count]) => (
                    <li key={status} className="flex justify-between">
                      <span className="text-ink-muted">{status}</span>
                      <span className="tabular-nums font-medium text-ink">{count}</span>
                    </li>
                  ))}
              </ul>
            </section>
            <section className="border border-line bg-surface p-5">
              <h2 className={HEAD}>Payment method</h2>
              <ul className="mt-4 space-y-2 text-sm">
                {Object.entries(data.payment_methods).map(([method, count]) => (
                  <li key={method} className="flex justify-between">
                    <span className="text-ink-muted">{method.replace("_", " ")}</span>
                    <span className="tabular-nums font-medium text-ink">{count}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <p className="text-[11px] text-stone">
            Cancelled orders are counted here. They are excluded from revenue figures,
            where counting them would overstate sales.
          </p>
        </>
      )}
    </div>
  );
}
