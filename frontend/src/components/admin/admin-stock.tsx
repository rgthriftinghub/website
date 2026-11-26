"use client";

/**
 * Stock levels, per-variant adjustment, movement history, and customer detail.
 *
 * Adjusting stock requires a reason: every change writes an inventory movement that
 * someone will later reconcile against, and "someone changed it" is not a reason.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  adjustVariantStock,
  getCustomerDetail,
  listInventoryHistory,
  listStock,
} from "@/lib/api/admin";
import { formatDateTime, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  CustomerDetail,
  InventoryMovement,
  StockRow,
} from "@/lib/api/types";

const FIELD =
  "w-full border border-line bg-paper px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-gold";
const TH = "px-4 py-3 text-left text-[11px] uppercase tracking-[0.12em] font-medium text-stone";
const HEAD = "text-[11px] font-semibold uppercase tracking-[0.14em] text-ink";

const STATUS_TONES: Record<string, string> = {
  in_stock: "bg-success/12 text-success",
  low: "bg-gold-wash text-gold-deep",
  out: "bg-danger/10 text-danger",
};
const STATUS_LABELS: Record<string, string> = {
  in_stock: "In stock",
  low: "Low",
  out: "Out",
};

const MOVEMENT_LABELS: Record<string, string> = {
  SALE: "Sale",
  RESTOCK: "Restock",
  ADJUSTMENT: "Adjustment",
  CANCELLED_ORDER: "Order cancelled",
  RETURN: "Return",
};

// ------------------------------------------------------------------ stock list
export function AdminStock() {
  const [rows, setRows] = useState<StockRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState<StockRow | null>(null);

  useEffect(() => {
    let cancelled = false;
    listStock({
      search: search || undefined,
      status: status || undefined,
      page,
      page_size: 50,
    })
      .then((result) => {
        if (cancelled) return;
        setRows(result.items);
        setTotal(result.total);
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      });
    return () => {
      cancelled = true;
    };
  }, [search, status, page, reloadKey]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <input
          defaultValue={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Search product or SKU"
          aria-label="Search stock"
          className={cn(FIELD, "max-w-xs")}
        />
        <div className="flex gap-1 border border-line bg-surface p-1">
          {[
            ["", "All"],
            ["out", "Out of stock"],
            ["low", "Low"],
            ["in_stock", "In stock"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setStatus(value);
                setPage(1);
              }}
              className={cn(
                "px-2.5 py-1.5 text-xs font-medium transition-colors",
                status === value ? "bg-ink text-paper" : "text-ink-muted hover:text-ink"
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <Link
          href="/admin/inventory/history"
          className="text-xs text-ink-muted underline decoration-gold/50 underline-offset-4"
        >
          Movement history
        </Link>
      </div>

      {rows === null ? (
        <p className="py-10 text-center text-sm text-stone">Loading stock…</p>
      ) : (
        <div className="overflow-x-auto border border-line bg-surface">
          <table className="w-full min-w-[48rem] text-sm">
            <thead>
              <tr className="border-b border-line">
                <th className={TH}>Product</th>
                <th className={TH}>Variant</th>
                <th className={TH}>SKU</th>
                <th className={cn(TH, "text-right")}>Stock</th>
                <th className={cn(TH, "text-right")}>Threshold</th>
                <th className={TH}>Status</th>
                <th className={TH}>Adjust</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.variant_id} className="border-b border-line/60">
                  <td className="px-4 py-2.5 text-ink">{row.product_name}</td>
                  <td className="px-4 py-2.5 text-ink-muted">{row.variant_label}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-stone">{row.sku}</td>
                  <td
                    className={cn(
                      "px-4 py-2.5 text-right tabular-nums font-medium",
                      row.quantity === 0 ? "text-danger" : "text-ink"
                    )}
                  >
                    {row.quantity}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-stone">
                    {row.low_stock_threshold}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        "inline-flex rounded-sm px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
                        STATUS_TONES[row.status]
                      )}
                    >
                      {STATUS_LABELS[row.status]}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <Button variant="ghost" onClick={() => setEditing(row)}>
                      Adjust
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-line px-4 py-3 text-sm text-ink-muted">
            <span>{total} variants</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={page * 50 >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}

      {editing ? (
        <AdjustPanel
          row={editing}
          onClose={() => setEditing(null)}
          onDone={() => {
            setEditing(null);
            setReloadKey((key) => key + 1);
          }}
        />
      ) : null}
    </div>
  );
}

function AdjustPanel({
  row,
  onClose,
  onDone,
}: {
  row: StockRow;
  onClose: () => void;
  onDone: () => void;
}) {
  const [mode, setMode] = useState<"add" | "remove" | "set">("add");
  const [quantity, setQuantity] = useState("1");
  const [threshold, setThreshold] = useState(String(row.low_stock_threshold));
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const amount = Number(quantity) || 0;
  const next =
    mode === "add"
      ? row.quantity + amount
      : mode === "remove"
        ? Math.max(row.quantity - amount, 0)
        : amount;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await adjustVariantStock(row.variant_id, {
        mode,
        quantity: amount,
        reason: reason.trim(),
        low_stock_threshold:
          Number(threshold) === row.low_stock_threshold ? undefined : Number(threshold),
      });
      onDone();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not adjust stock.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className={HEAD}>
            Adjust · {row.product_name} · {row.variant_label}
          </h2>
          <p className="mt-1 text-xs text-stone">
            SKU {row.sku} · currently {row.quantity} in stock
          </p>
        </div>
        <Button type="button" variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-stone">
            Operation
          </span>
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value as typeof mode)}
            className={FIELD}
          >
            <option value="add">Add</option>
            <option value="remove">Remove</option>
            <option value="set">Set to</option>
          </select>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-stone">
            Quantity
          </span>
          <input
            type="number"
            min="0"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            className={FIELD}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-stone">
            Threshold
          </span>
          <input
            type="number"
            min="0"
            value={threshold}
            onChange={(event) => setThreshold(event.target.value)}
            className={FIELD}
          />
        </label>
        <div className="flex flex-col gap-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-stone">
            Result
          </span>
          <p className="py-2 font-serif text-xl text-ink">
            {row.quantity} → {next}
          </p>
        </div>
      </div>

      <label className="mt-4 flex flex-col gap-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-stone">
          Reason (required)
        </span>
        <input
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Received new shipment"
          required
          minLength={3}
          className={FIELD}
        />
      </label>

      {error ? (
        <p role="alert" className="mt-3 text-sm text-danger">
          {error}
        </p>
      ) : null}

      <Button type="submit" className="mt-4" disabled={busy || reason.trim().length < 3}>
        {busy ? "Saving…" : "Record adjustment"}
      </Button>
      <p className="mt-2 text-[11px] text-stone">
        Recorded in the inventory history with the before and after quantities.
      </p>
    </form>
  );
}

// ------------------------------------------------------------------- history
export function AdminInventoryHistory() {
  const [rows, setRows] = useState<InventoryMovement[] | null>(null);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    let cancelled = false;
    listInventoryHistory({
      search: search || undefined,
      type: type || undefined,
      page,
      page_size: 50,
    })
      .then((result) => {
        if (cancelled) return;
        setRows(result.items);
        setTotal(result.total);
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      });
    return () => {
      cancelled = true;
    };
  }, [search, type, page]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <input
          defaultValue={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Search product or SKU"
          aria-label="Search movements"
          className={cn(FIELD, "max-w-xs")}
        />
        <select
          value={type}
          onChange={(event) => {
            setType(event.target.value);
            setPage(1);
          }}
          aria-label="Filter by movement type"
          className={cn(FIELD, "max-w-[12rem]")}
        >
          <option value="">All types</option>
          {Object.entries(MOVEMENT_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <Link
          href="/admin/inventory"
          className="text-xs text-ink-muted underline decoration-gold/50 underline-offset-4"
        >
          Back to stock
        </Link>
      </div>

      {rows === null ? (
        <p className="py-10 text-center text-sm text-stone">Loading history…</p>
      ) : rows.length === 0 ? (
        <p className="border border-line bg-surface py-12 text-center text-sm text-stone">
          No movements recorded yet.
        </p>
      ) : (
        <div className="overflow-x-auto border border-line bg-surface">
          <table className="w-full min-w-[54rem] text-sm">
            <thead>
              <tr className="border-b border-line">
                <th className={TH}>When</th>
                <th className={TH}>Product</th>
                <th className={TH}>SKU</th>
                <th className={TH}>Type</th>
                <th className={cn(TH, "text-right")}>Change</th>
                <th className={cn(TH, "text-right")}>Before</th>
                <th className={cn(TH, "text-right")}>After</th>
                <th className={TH}>Reason</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-line/60">
                  <td className="whitespace-nowrap px-4 py-2.5 text-xs text-stone">
                    {formatDateTime(row.created_at)}
                  </td>
                  <td className="px-4 py-2.5 text-ink">{row.product_name}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-stone">{row.sku}</td>
                  <td className="px-4 py-2.5 text-ink-muted">
                    {MOVEMENT_LABELS[row.type] ?? row.type}
                  </td>
                  <td
                    className={cn(
                      "px-4 py-2.5 text-right tabular-nums font-medium",
                      row.quantity_change > 0 ? "text-success" : "text-danger"
                    )}
                  >
                    {row.quantity_change > 0 ? "+" : ""}
                    {row.quantity_change}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-stone">
                    {row.quantity_before}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-ink">
                    {row.quantity_after}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-ink-muted">{row.note ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-line px-4 py-3 text-sm text-ink-muted">
            <span>{total} movements</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={page * 50 >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}
      <p className="text-[11px] text-stone">
        Append-only. Current stock can always be reconciled against this trail.
      </p>
    </div>
  );
}

// ------------------------------------------------------------- customer detail
export function AdminCustomerDetail({ customerId }: { customerId: string }) {
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCustomerDetail(customerId)
      .then((result) => {
        if (!cancelled) setCustomer(result);
      })
      .catch(() => {
        if (!cancelled) setNotFound(true);
      });
    return () => {
      cancelled = true;
    };
  }, [customerId]);

  if (notFound) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-ink-muted">That customer could not be found.</p>
        <Link
          href="/admin/customers"
          className="mt-3 inline-block text-sm text-ink underline decoration-gold/50 underline-offset-4"
        >
          Back to customers
        </Link>
      </div>
    );
  }

  if (!customer) {
    return <p className="py-10 text-center text-sm text-stone">Loading customer…</p>;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-px overflow-hidden border border-line bg-line sm:grid-cols-4">
        {[
          ["Orders", String(customer.order_count)],
          ["Total spent", formatPrice(customer.total_spent)],
          ["Segment", customer.segment],
          [
            "Last order",
            customer.last_order_at ? formatDateTime(customer.last_order_at) : "—",
          ],
        ].map(([label, value]) => (
          <div key={label} className="bg-surface px-4 py-3.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone">
              {label}
            </p>
            <p className="mt-1 font-serif text-lg text-ink">{value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-6">
          <section className="border border-line bg-surface">
            <h2 className={cn(HEAD, "border-b border-line px-5 py-3.5")}>
              Order history
            </h2>
            {customer.orders.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-stone">No orders yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[34rem] text-sm">
                  <thead>
                    <tr className="border-b border-line">
                      <th className={TH}>Order</th>
                      <th className={TH}>Placed</th>
                      <th className={TH}>Status</th>
                      <th className={TH}>Payment</th>
                      <th className={cn(TH, "text-right")}>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {customer.orders.map((order) => (
                      <tr key={order.id} className="border-b border-line/60">
                        <td className="px-4 py-2.5">
                          <Link
                            href={`/admin/orders/${order.id}`}
                            className="font-mono text-xs text-ink underline decoration-gold/50 underline-offset-4"
                          >
                            {order.order_number}
                          </Link>
                        </td>
                        <td className="px-4 py-2.5 text-xs text-stone">
                          {formatDateTime(order.created_at)}
                        </td>
                        <td className="px-4 py-2.5 text-ink-muted">{order.order_status}</td>
                        <td className="px-4 py-2.5 text-ink-muted">{order.payment_status}</td>
                        <td className="px-4 py-2.5 text-right tabular-nums font-medium text-ink">
                          {formatPrice(order.total_amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {customer.notes.length > 0 ? (
            <section className="border border-line bg-surface p-5">
              <h2 className={HEAD}>Private notes</h2>
              <ul className="mt-3 space-y-3">
                {customer.notes.map((note) => (
                  <li key={note.id} className="text-sm">
                    <p className="text-ink">{note.body}</p>
                    <p className="mt-0.5 text-xs text-stone">
                      {note.author_email ?? "system"} · {formatDateTime(note.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-[11px] text-stone">
                Internal only. Add notes from the customers list.
              </p>
            </section>
          ) : null}
        </div>

        <aside className="space-y-4">
          <section className="border border-line bg-surface p-5">
            <h2 className={HEAD}>Profile</h2>
            <dl className="mt-3 space-y-2 text-sm">
              <div>
                <dt className="text-xs text-stone">Name</dt>
                <dd className="text-ink">
                  {customer.first_name} {customer.last_name}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-stone">Email</dt>
                <dd className="text-ink">{customer.email}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone">Phone</dt>
                <dd className="text-ink">{customer.phone ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone">Joined</dt>
                <dd className="text-ink-muted">{formatDateTime(customer.created_at)}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone">Last sign-in</dt>
                <dd className="text-ink-muted">
                  {customer.last_login_at ? formatDateTime(customer.last_login_at) : "—"}
                </dd>
              </div>
            </dl>
          </section>

          {customer.addresses.length > 0 ? (
            <section className="border border-line bg-surface p-5">
              <h2 className={HEAD}>Addresses</h2>
              <ul className="mt-3 space-y-3 text-sm">
                {customer.addresses.map((address) => (
                  <li key={address.id}>
                    <p className="text-ink">{address.full_name}</p>
                    <p className="text-xs leading-relaxed text-ink-muted">
                      {address.address_line_1}
                      {address.address_line_2 ? `, ${address.address_line_2}` : ""}
                      <br />
                      {address.city}, {address.province}
                      <br />
                      {address.phone}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {customer.wishlist.length > 0 ? (
            <section className="border border-line bg-surface p-5">
              <h2 className={HEAD}>Wishlist</h2>
              <ul className="mt-3 space-y-1 text-sm text-ink-muted">
                {customer.wishlist.map((name, index) => (
                  <li key={`${name}-${index}`}>{name}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
