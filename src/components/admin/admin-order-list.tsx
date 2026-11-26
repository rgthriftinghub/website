"use client";

import Link from "next/link";
import { Filter, X } from "lucide-react";
import { useEffect, useState } from "react";

import {
  ORDER_STATUS_LABELS,
  OrderStatusPill,
  PAYMENT_METHOD_LABELS,
  PaymentStatusPill,
} from "@/components/orders/order-status";
import { listAdminOrders, getAdminOrderStats } from "@/lib/api/commerce";
import type {
  AdminOrderQuery,
  AdminOrderSummary,
  OrderStats,
  OrderStatus,
  Page,
  PaymentStatus,
} from "@/lib/api/types";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

const STATUSES: OrderStatus[] = [
  "PENDING",
  "PROCESSING",
  "PACKED",
  "DISPATCHED",
  "DELIVERED",
  "CANCELLED",
  "RETURNED",
  "EXCHANGE",
];

const PAYMENT_STATUSES: PaymentStatus[] = ["PENDING", "PAID", "FAILED", "REFUNDED"];

const PAGE_SIZE = 20;

const EMPTY_FILTERS: AdminOrderQuery = {};

export function AdminOrderList() {
  const [filters, setFilters] = useState<AdminOrderQuery>(EMPTY_FILTERS);
  const [draftCustomer, setDraftCustomer] = useState("");
  const [draftOrderNumber, setDraftOrderNumber] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<AdminOrderSummary> | null>(null);
  const [stats, setStats] = useState<OrderStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminOrderStats().then(setStats).catch(() => setStats(null));
  }, []);

  useEffect(() => {
    let cancelled = false;
    listAdminOrders({ ...filters, page, page_size: PAGE_SIZE })
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load orders.");
      });
    return () => {
      cancelled = true;
    };
  }, [filters, page]);

  function setFilter<K extends keyof AdminOrderQuery>(key: K, value: AdminOrderQuery[K]) {
    // Any filter change returns to page 1; staying deep in a narrower result set
    // would show an empty table.
    setPage(1);
    setFilters((current) => {
      const next = { ...current };
      if (value === undefined || value === "") delete next[key];
      else next[key] = value;
      return next;
    });
  }

  const activeCount = Object.keys(filters).length;

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Operations</p>
          <h1 className="mt-2 text-3xl">Orders</h1>
          <p className="mt-2 text-sm text-ink-muted">
            {data ? `${data.total} order${data.total === 1 ? "" : "s"}` : "Loading…"}
          </p>
        </div>
      </header>

      {/* Status counts double as one-click filters. */}
      {stats ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <div className="border border-line bg-surface p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-stone">
              Total orders
            </p>
            <p className="mt-1.5 font-display text-2xl">{stats.total_orders}</p>
          </div>
          <div className="border border-line bg-surface p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-stone">
              Revenue (excl. cancelled)
            </p>
            <p className="mt-1.5 font-display text-2xl">{formatPrice(stats.revenue_total)}</p>
          </div>
          {(["PENDING", "PROCESSING", "DISPATCHED"] as OrderStatus[]).map((status) => (
            <button
              key={status}
              type="button"
              onClick={() => setFilter("status", filters.status === status ? undefined : status)}
              className={cn(
                "border p-4 text-left transition-colors",
                filters.status === status
                  ? "border-ink bg-ink text-paper"
                  : "border-line bg-surface hover:border-gold"
              )}
            >
              <p
                className={cn(
                  "text-[10px] font-semibold uppercase tracking-[0.12em]",
                  filters.status === status ? "text-paper/70" : "text-stone"
                )}
              >
                {ORDER_STATUS_LABELS[status]}
              </p>
              <p className="mt-1.5 font-display text-2xl">{stats.status_counts[status] ?? 0}</p>
            </button>
          ))}
        </div>
      ) : null}

      {/* Filters */}
      <section className="mt-6 border border-line bg-surface p-5">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
            <Filter className="size-3.5 text-gold-deep" aria-hidden />
            Filters
          </h2>
          {activeCount > 0 ? (
            <button
              type="button"
              onClick={() => {
                setFilters(EMPTY_FILTERS);
                setDraftCustomer("");
                setDraftOrderNumber("");
                setPage(1);
              }}
              className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-gold-deep hover:text-ink"
            >
              <X className="size-3" aria-hidden />
              Clear {activeCount}
            </button>
          ) : null}
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Select
            label="Order status"
            value={filters.status ?? ""}
            onChange={(value) => setFilter("status", (value || undefined) as OrderStatus)}
            options={STATUSES.map((status) => ({ value: status, label: ORDER_STATUS_LABELS[status] }))}
          />
          <Select
            label="Payment status"
            value={filters.payment_status ?? ""}
            onChange={(value) =>
              setFilter("payment_status", (value || undefined) as PaymentStatus)
            }
            options={PAYMENT_STATUSES.map((status) => ({ value: status, label: status }))}
          />
          <div className="grid grid-cols-2 gap-2">
            <DateInput
              label="From"
              value={filters.date_from ?? ""}
              onChange={(value) => setFilter("date_from", value || undefined)}
            />
            <DateInput
              label="To"
              value={filters.date_to ?? ""}
              onChange={(value) => setFilter("date_to", value || undefined)}
            />
          </div>
          <SearchInput
            label="Customer"
            placeholder="Name or email"
            value={draftCustomer}
            onValueChange={setDraftCustomer}
            onSubmit={() => setFilter("customer", draftCustomer.trim() || undefined)}
          />
          <SearchInput
            label="Order number"
            placeholder="RG-20260812-0001"
            value={draftOrderNumber}
            onValueChange={setDraftOrderNumber}
            onSubmit={() => setFilter("order_number", draftOrderNumber.trim() || undefined)}
          />
        </div>
      </section>

      {error ? <p className="mt-6 text-sm text-danger">{error}</p> : null}

      {data ? (
        <>
          <div className="mt-6 overflow-x-auto border border-line bg-surface">
            <table className="w-full min-w-[52rem] text-left text-sm">
              <thead className="border-b border-line bg-paper-alt">
                <tr className="text-[10px] uppercase tracking-[0.12em] text-ink-muted">
                  <th scope="col" className="px-4 py-3 font-semibold">Order</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Customer</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Date</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Items</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Total</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Status</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Payment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.items.map((order) => (
                  <tr key={order.id} className="hover:bg-paper-alt/60">
                    <td className="px-4 py-3">
                      <Link
                        href={`/admin/orders/${order.id}`}
                        className="font-mono text-xs font-semibold text-ink hover:text-gold-deep"
                      >
                        {order.order_number}
                      </Link>
                      <p className="mt-0.5 text-[11px] text-stone">
                        {PAYMENT_METHOD_LABELS[order.payment_method]}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-ink">
                        {order.customer.is_guest ? "Guest · " : ""}{order.customer.first_name} {order.customer.last_name}
                      </p>
                      <p className="text-[11px] text-stone">{order.customer.email ?? "No email provided"}</p>
                    </td>
                    <td className="px-4 py-3 text-xs text-ink-muted">
                      {new Date(order.created_at).toLocaleDateString("en-PK", {
                        dateStyle: "medium",
                      })}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-ink">{order.item_count}</td>
                    <td className="px-4 py-3 tabular-nums text-ink">
                      {formatPrice(order.total_amount)}
                    </td>
                    <td className="px-4 py-3">
                      <OrderStatusPill status={order.order_status} />
                    </td>
                    <td className="px-4 py-3">
                      <PaymentStatusPill status={order.payment_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.items.length === 0 ? (
            <p className="mt-6 text-sm text-ink-muted">No orders match those filters.</p>
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

const FIELD_CLASS =
  "mt-1.5 h-10 w-full border border-line bg-surface px-2.5 text-sm text-ink outline-none focus:border-gold";
const LABEL_CLASS = "text-[10px] font-semibold uppercase tracking-[0.12em] text-stone";

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <span className={LABEL_CLASS}>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={FIELD_CLASS}>
        <option value="">All</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function DateInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className={LABEL_CLASS}>{label}</span>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={FIELD_CLASS}
      />
    </label>
  );
}

function SearchInput({
  label,
  placeholder,
  value,
  onValueChange,
  onSubmit,
}: {
  label: string;
  placeholder: string;
  value: string;
  onValueChange: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <label className="block">
      <span className={LABEL_CLASS}>{label}</span>
      <input
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onValueChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            onSubmit();
          }
        }}
        onBlur={onSubmit}
        className={FIELD_CLASS}
      />
    </label>
  );
}
