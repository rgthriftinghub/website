"use client";

import { MediaImage as Image } from "@/components/ui/media-image";
import Link from "next/link";
import { ArrowLeft, FileText, Loader2, Save } from "lucide-react";
import { useEffect, useState } from "react";

import {
  ORDER_STATUS_LABELS,
  OrderStatusPill,
  OrderTimeline,
  PAYMENT_METHOD_LABELS,
  PaymentStatusPill,
} from "@/components/orders/order-status";
import { AdminShippingPanel } from "@/components/admin/admin-shipping-panel";
import { errorMessage } from "@/components/providers/store-provider";
import { Button } from "@/components/ui/button";
import {
  adminInvoiceUrl,
  decideReturnRequest,
  getAdminOrder,
  getOrderInventoryImpact,
  updateOrderInternalNote,
  updateOrderPaymentStatus,
  updateOrderStatus,
} from "@/lib/api/commerce";
import type {
  AdminOrder,
  InventoryTransaction,
  OrderStatus,
  PaymentStatus,
} from "@/lib/api/types";
import { formatPrice } from "@/lib/format";

/**
 * Forward transitions offered per status, mirroring the backend's transition
 * table. The server validates independently, so this only shapes the UI.
 */
const NEXT_STATUSES: Partial<Record<OrderStatus, OrderStatus[]>> = {
  PENDING: ["PROCESSING", "CANCELLED"],
  PROCESSING: ["PACKED", "CANCELLED"],
  PACKED: ["DISPATCHED", "CANCELLED"],
  DISPATCHED: ["DELIVERED"],
  DELIVERED: [],
};

const PAYMENT_STATUSES: PaymentStatus[] = ["PENDING", "PAID", "FAILED", "REFUNDED"];

export function AdminOrderDetail({ orderId }: { orderId: string }) {
  const [order, setOrder] = useState<AdminOrder | null>(null);
  const [movements, setMovements] = useState<InventoryTransaction[]>([]);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [noteSaved, setNoteSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAdminOrder(orderId)
      .then(async (result) => {
        if (cancelled) return;
        setOrder(result);
        setNote(result.internal_note ?? "");
        const impact = await getOrderInventoryImpact(orderId).catch(() => []);
        if (!cancelled) setMovements(impact);
      })
      .catch(() => {
        if (!cancelled) setNotFound(true);
      });
    return () => {
      cancelled = true;
    };
  }, [orderId]);

  async function run(action: () => Promise<AdminOrder>) {
    setBusy(true);
    setError(null);
    try {
      const updated = await action();
      setOrder(updated);
      setMovements(await getOrderInventoryImpact(orderId).catch(() => []));
    } catch (caught) {
      setError(errorMessage(caught, "That change could not be applied."));
    } finally {
      setBusy(false);
    }
  }

  if (notFound) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-2xl">Order not found</h1>
        <Link
          href="/admin/orders"
          className="mt-5 inline-block text-xs font-semibold uppercase tracking-[0.12em] text-gold-deep"
        >
          Back to orders
        </Link>
      </div>
    );
  }

  if (order === null) {
    return (
      <p className="py-20 text-sm text-stone" role="status">
        Loading order…
      </p>
    );
  }

  const nextStatuses = NEXT_STATUSES[order.order_status] ?? [];

  return (
    <>
      <Link
        href="/admin/orders"
        className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted hover:text-ink"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        All orders
      </Link>

      <header className="mt-5 flex flex-wrap items-start justify-between gap-4 border-b border-line pb-6">
        <div>
          <p className="eyebrow">Order</p>
          <h1 className="mt-2 font-mono text-3xl">{order.order_number}</h1>
          <p className="mt-2 text-sm text-ink-muted">
            {new Date(order.created_at).toLocaleString("en-PK", {
              dateStyle: "long",
              timeStyle: "short",
            })}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <OrderStatusPill status={order.order_status} />
            <PaymentStatusPill status={order.payment_status} />
          </div>
        </div>
        <div className="text-right">
          <p className="font-display text-3xl">{formatPrice(order.total_amount)}</p>
          <Link
            href={adminInvoiceUrl(order.id)}
            target="_blank"
            rel="noopener"
            className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-gold-deep hover:text-ink"
          >
            <FileText className="size-3.5" aria-hidden />
            Invoice
          </Link>
        </div>
      </header>

      {error ? (
        <p role="alert" className="mt-6 border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="mt-8 lg:grid lg:grid-cols-[1fr_20rem] lg:gap-8">
        <div className="space-y-6">
          {/* Status controls */}
          <section className="border border-line bg-surface p-5">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Update status
            </h2>
            {nextStatuses.length > 0 ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {nextStatuses.map((status) => (
                  <Button
                    key={status}
                    size="sm"
                    variant={status === "CANCELLED" ? "secondary" : "primary"}
                    disabled={busy}
                    onClick={() => {
                      const note =
                        status === "CANCELLED"
                          ? window.prompt("Reason for cancelling (optional):") ?? undefined
                          : undefined;
                      void run(() => updateOrderStatus(order.id, status, note || undefined));
                    }}
                  >
                    {busy ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
                    Mark {ORDER_STATUS_LABELS[status]}
                  </Button>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-ink-muted">
                No further status changes are available from {ORDER_STATUS_LABELS[order.order_status]}.
              </p>
            )}
            {nextStatuses.includes("CANCELLED") ? (
              <p className="mt-3 text-xs text-stone">
                Cancelling returns every item&rsquo;s stock to the catalogue and records the
                movement.
              </p>
            ) : null}
          </section>

          {/* Payment */}
          <section className="border border-line bg-surface p-5">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Payment
            </h2>
            <p className="mt-3 text-sm text-ink">
              {PAYMENT_METHOD_LABELS[order.payment_method]} · currently{" "}
              {order.payment_status.toLowerCase()}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {PAYMENT_STATUSES.filter((status) => status !== order.payment_status).map(
                (status) => (
                  <Button
                    key={status}
                    size="sm"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => void run(() => updateOrderPaymentStatus(order.id, status))}
                  >
                    {status === "PAID" && (order.payment_method === "JAZZCASH" || order.payment_method === "EASYPAISA")
                      ? "Confirm Order"
                      : `Mark ${status.toLowerCase()}`}
                  </Button>
                )
              )}
            </div>
            <p className="mt-3 text-xs text-stone">
              Mark paid only once cash has been collected or a transfer reconciled.
            </p>
          </section>

          {/* Items */}
          <section>
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Items
            </h2>
            <ul className="mt-3 divide-y divide-line border border-line bg-surface">
              {order.items.map((item) => (
                <li key={item.id} className="flex gap-4 p-4">
                  <div className="relative w-14 shrink-0 overflow-hidden bg-paper-alt aspect-[3/4]">
                    {item.image_url_snapshot ? (
                      <Image
                        src={item.image_url_snapshot}
                        alt=""
                        fill
                        sizes="56px"
                        className="object-cover"
                      />
                    ) : null}
                  </div>
                  <div className="min-w-0 flex-1 text-sm">
                    <p className="truncate text-ink">{item.product_name_snapshot}</p>
                    <p className="mt-0.5 text-xs text-stone">
                      {item.brand_name_snapshot ? `${item.brand_name_snapshot} · ` : ""}
                      {item.variant_label} · {item.sku_snapshot}
                    </p>
                  </div>
                  <div className="shrink-0 text-right text-sm">
                    <p className="tabular-nums text-ink">{formatPrice(item.line_total)}</p>
                    <p className="text-xs text-stone">
                      {item.quantity} × {formatPrice(item.unit_price)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>

            <dl className="mt-4 ml-auto max-w-xs space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-muted">Subtotal</dt>
                <dd className="tabular-nums">{formatPrice(order.subtotal)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">Delivery</dt>
                <dd className="tabular-nums">{formatPrice(order.shipping_amount)}</dd>
              </div>
              <div className="flex items-baseline justify-between border-t border-line pt-2">
                <dt className="font-semibold text-ink">Total</dt>
                <dd className="font-display text-xl">{formatPrice(order.total_amount)}</dd>
              </div>
            </dl>
          </section>

          {/* Inventory impact */}
          <section>
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Inventory impact
            </h2>
            {movements.length === 0 ? (
              <p className="mt-3 text-sm text-ink-muted">No stock movements recorded.</p>
            ) : (
              <ul className="mt-3 divide-y divide-line border border-line bg-surface text-sm">
                {movements.map((movement) => (
                  <li key={movement.id} className="flex items-center justify-between gap-4 p-4">
                    <div>
                      <p className="text-ink">{movement.type.replace("_", " ")}</p>
                      <p className="text-xs text-stone">
                        {new Date(movement.created_at).toLocaleString("en-PK", {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                        {movement.note ? ` · ${movement.note}` : ""}
                      </p>
                    </div>
                    <p className="shrink-0 font-mono text-xs text-ink">
                      <span
                        className={
                          movement.quantity_change < 0 ? "text-danger" : "text-success"
                        }
                      >
                        {movement.quantity_change > 0 ? "+" : ""}
                        {movement.quantity_change}
                      </span>{" "}
                      ({movement.quantity_before} → {movement.quantity_after})
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Returns */}
          {order.return_requests.length > 0 ? (
            <section>
              <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
                Return &amp; exchange requests
              </h2>
              <ul className="mt-3 space-y-2">
                {order.return_requests.map((request) => (
                  <li key={request.id} className="border border-line bg-surface p-4 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-ink">
                        {request.type === "RETURN" ? "Return" : "Exchange"} · {request.reason}
                      </span>
                      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-gold-deep">
                        {request.status}
                      </span>
                    </div>
                    {request.description ? (
                      <p className="mt-1.5 text-xs text-ink-muted">{request.description}</p>
                    ) : null}
                    {request.status === "REQUESTED" || request.status === "APPROVED" ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(["APPROVED", "REJECTED", "COMPLETED"] as const)
                          .filter((decision) => decision !== request.status)
                          .map((decision) => (
                            <Button
                              key={decision}
                              size="sm"
                              variant="secondary"
                              disabled={busy}
                              onClick={() => {
                                const resolution =
                                  window.prompt("Resolution note (optional):") ?? undefined;
                                void run(async () => {
                                  await decideReturnRequest(
                                    request.id,
                                    decision,
                                    resolution || undefined
                                  );
                                  return getAdminOrder(order.id);
                                });
                              }}
                            >
                              {decision.toLowerCase()}
                            </Button>
                          ))}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>

        {/* Sidebar */}
        <aside className="mt-8 space-y-4 lg:mt-0">
          <section className="border border-line bg-surface p-5">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Customer
            </h2>
            <p className="mt-3 text-sm font-medium text-ink">
              {order.customer.is_guest ? "Guest · " : ""}{order.customer.first_name} {order.customer.last_name}
            </p>
            <p className="text-sm text-ink-muted">{order.customer.email ?? "No email provided"}</p>
            <p className="mt-1 text-sm text-ink-muted">{order.contact_phone}</p>
          </section>

          <section className="border border-line bg-surface p-5">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Delivery address
            </h2>
            <address className="mt-3 text-sm not-italic leading-relaxed text-ink-muted">
              <span className="block font-medium text-ink">
                {order.shipping_address_snapshot.full_name}
              </span>
              {order.shipping_address_snapshot.address_line_1}
              {order.shipping_address_snapshot.address_line_2 ? (
                <>, {order.shipping_address_snapshot.address_line_2}</>
              ) : null}
              <br />
              {order.shipping_address_snapshot.city}, {order.shipping_address_snapshot.province}
              {order.shipping_address_snapshot.postal_code
                ? ` ${order.shipping_address_snapshot.postal_code}`
                : ""}
              <br />
              {order.shipping_address_snapshot.phone}
            </address>
          </section>

          {/* Courier and shipping status. Kept separate from the order timeline
              above, because shipping progresses on its own clock. */}
          <AdminShippingPanel orderId={orderId} shipment={order.shipment} />

          <section className="border border-line bg-surface p-5">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Timeline
            </h2>
            <div className="mt-4">
              <OrderTimeline status={order.order_status} events={order.status_events} />
            </div>
          </section>

          {order.customer_note ? (
            <section className="border border-line bg-gold-wash p-5">
              <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
                Customer note
              </h2>
              <p className="mt-2 text-sm text-ink-muted">{order.customer_note}</p>
            </section>
          ) : null}

          <section className="border border-line bg-surface p-5">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Internal note
            </h2>
            <p className="mt-1 text-xs text-stone">Staff only — never shown to the customer.</p>
            <textarea
              value={note}
              onChange={(event) => {
                setNote(event.target.value);
                setNoteSaved(false);
              }}
              rows={4}
              maxLength={2000}
              className="mt-3 w-full border border-line bg-paper px-3 py-2 text-sm outline-none focus:border-gold"
            />
            <Button
              size="sm"
              variant="secondary"
              className="mt-2 w-full"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  const updated = await updateOrderInternalNote(order.id, note.trim() || null);
                  setNoteSaved(true);
                  return updated;
                })
              }
            >
              <Save className="size-3.5" aria-hidden />
              {noteSaved ? "Saved" : "Save note"}
            </Button>
          </section>
        </aside>
      </div>
    </>
  );
}
