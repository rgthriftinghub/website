"use client";

import { MediaImage as Image } from "@/components/ui/media-image";
import Link from "next/link";
import { FileText, Loader2, RotateCcw, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import {
  OrderStatusPill,
  OrderTimeline,
  PAYMENT_METHOD_LABELS,
  PaymentStatusPill,
} from "@/components/orders/order-status";
import { ShipmentPanel } from "@/components/orders/shipping-status";
import { errorMessage, useStore } from "@/components/providers/store-provider";
import { submitBankTransfer } from "@/lib/api/payments";
import { Button, ButtonLink } from "@/components/ui/button";
import { cancelMyOrder, getMyOrder, myInvoiceUrl, requestReturn } from "@/lib/api/commerce";
import type { Order, ReturnRequestType } from "@/lib/api/types";
import { formatPrice } from "@/lib/format";

/**
 * Bank transfer reference submission.
 *
 * The customer tells us what they sent; staff reconcile it against the bank
 * statement. Submitting queues the payment for verification and never marks it
 * paid — that would let a customer settle their own order.
 */
function BankTransferForm({
  orderNumber,
  submittedReference,
  onSubmitted,
}: {
  orderNumber: string;
  submittedReference: string | null;
  onSubmitted: () => void;
}) {
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  if (submittedReference && !open) {
    return (
      <div className="mt-4 border-t border-line pt-4">
        <p className="text-xs uppercase tracking-[0.12em] text-stone">
          Your reference
        </p>
        <p className="mt-1 font-mono text-sm text-ink">{submittedReference}</p>
        <p className="mt-2 text-xs text-ink-muted">
          We are checking this against our bank statement and will confirm shortly.
        </p>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="mt-2 text-xs text-ink underline decoration-gold/60 underline-offset-4"
        >
          Update reference
        </button>
      </div>
    );
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await submitBankTransfer(orderNumber, {
        reference: reference.trim(),
        note: note.trim() || null,
      });
      setOpen(false);
      onSubmitted();
    } catch (caught) {
      setError(errorMessage(caught, "Could not submit your reference."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 border-t border-line pt-4">
      <label className="flex flex-col gap-1.5">
        <span className="text-xs uppercase tracking-[0.12em] text-stone">
          Transfer reference
        </span>
        <input
          value={reference}
          onChange={(event) => setReference(event.target.value)}
          placeholder="e.g. TRX-83719204"
          required
          minLength={3}
          className="w-full border border-line bg-paper px-3 py-2 font-mono text-sm text-ink outline-none transition-colors placeholder:text-stone focus:border-gold"
        />
      </label>
      <label className="mt-3 flex flex-col gap-1.5">
        <span className="text-xs uppercase tracking-[0.12em] text-stone">
          Note <span className="normal-case">(optional)</span>
        </span>
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          placeholder="Which bank you sent it from"
          className="w-full border border-line bg-paper px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-stone focus:border-gold"
        />
      </label>
      {error ? (
        <p role="alert" className="mt-2 text-xs text-danger">
          {error}
        </p>
      ) : null}
      <Button
        type="submit"
        disabled={busy || reference.trim().length < 3}
        className="mt-3 w-full"
      >
        {busy ? "Submitting…" : "Submit reference"}
      </Button>
      <p className="mt-2 text-[11px] leading-relaxed text-stone">
        We verify every transfer manually before confirming your order.
      </p>
    </form>
  );
}

export function OrderDetailView({ orderNumber }: { orderNumber: string }) {
  const { refreshCart } = useStore();
  const [order, setOrder] = useState<Order | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showReturnForm, setShowReturnForm] = useState(false);

  // Bumped by actions that need the order re-fetched (submitting a bank transfer
  // reference). Incrementing from an event handler keeps the effect free of any
  // synchronous state update.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getMyOrder(orderNumber)
      .then((result) => {
        if (!cancelled) setOrder(result);
      })
      .catch(() => {
        if (!cancelled) setNotFound(true);
      });
    return () => {
      cancelled = true;
    };
  }, [orderNumber, reloadKey]);

  async function handleCancel() {
    if (!order) return;
    const reason = window.prompt("Tell us why you are cancelling (optional):") ?? undefined;
    setBusy(true);
    setError(null);
    try {
      setOrder(await cancelMyOrder(order.order_number, reason || undefined));
      // Stock went back to the catalogue, so any bag preview should resync.
      await refreshCart();
    } catch (caught) {
      setError(errorMessage(caught, "Could not cancel this order."));
    } finally {
      setBusy(false);
    }
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <h1 className="font-display text-3xl">Order not found</h1>
        <p className="mt-3 text-sm text-ink-muted">
          We could not find that order on your account.
        </p>
        <ButtonLink href="/account/orders" className="mt-8">
          Your orders
        </ButtonLink>
      </div>
    );
  }

  if (order === null) {
    return (
      <div className="grid place-items-center py-28">
        <p className="text-sm text-stone" role="status">
          Loading order…
        </p>
      </div>
    );
  }

  const openReturn = order.return_requests.find(
    (request) => request.status === "REQUESTED" || request.status === "APPROVED"
  );
  const canRequestReturn = order.order_status === "DELIVERED" && !openReturn;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="border-b border-line pb-6">
        <Link
          href="/account/orders"
          className="text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted hover:text-ink"
        >
          ← Your orders
        </Link>
        <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow">Order</p>
            <h1 className="mt-2 font-mono text-3xl sm:text-4xl">{order.order_number}</h1>
            <p className="mt-2 text-sm text-ink-muted">
              Placed{" "}
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
              href={myInvoiceUrl(order.order_number)}
              target="_blank"
              rel="noopener"
              className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-gold-deep hover:text-ink"
            >
              <FileText className="size-3.5" aria-hidden />
              Invoice
            </Link>
          </div>
        </div>
      </header>

      {error ? (
        <p role="alert" className="mt-6 border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="mt-8 lg:grid lg:grid-cols-[1fr_19rem] lg:gap-10">
        <div>
          {/* Items */}
          <section>
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Items
            </h2>
            <ul className="mt-3 divide-y divide-line border-y border-line">
              {order.items.map((item) => (
                <li key={item.id} className="flex gap-4 py-5">
                  <div className="relative w-20 shrink-0 overflow-hidden bg-paper-alt aspect-[3/4]">
                    {item.image_url_snapshot ? (
                      <Image
                        src={item.image_url_snapshot}
                        alt={item.product_name_snapshot}
                        fill
                        sizes="80px"
                        className="object-cover"
                      />
                    ) : null}
                  </div>
                  <div className="min-w-0 flex-1">
                    {item.brand_name_snapshot ? (
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-gold-deep">
                        {item.brand_name_snapshot}
                      </p>
                    ) : null}
                    {/* Snapshot values, so this reads the same years later. */}
                    <h3 className="mt-1 font-display text-base leading-snug">
                      <Link
                        href={`/shop/${item.product_slug_snapshot}`}
                        className="hover:text-gold-deep"
                      >
                        {item.product_name_snapshot}
                      </Link>
                    </h3>
                    <p className="mt-1.5 text-xs text-ink-muted">
                      {item.variant_label} · Qty {item.quantity}
                    </p>
                    <p className="mt-0.5 font-mono text-[11px] text-stone">{item.sku_snapshot}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-sm font-semibold tabular-nums text-ink">
                      {formatPrice(item.line_total)}
                    </p>
                    {item.quantity > 1 ? (
                      <p className="text-xs text-stone">{formatPrice(item.unit_price)} each</p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>

            <dl className="mt-5 ml-auto max-w-xs space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-muted">Subtotal</dt>
                <dd className="tabular-nums">{formatPrice(order.subtotal)}</dd>
              </div>
              {Number(order.discount_amount) > 0 ? (
                <div className="flex justify-between">
                  <dt className="text-ink-muted">Discount</dt>
                  <dd className="tabular-nums">−{formatPrice(order.discount_amount)}</dd>
                </div>
              ) : null}
              <div className="flex justify-between">
                <dt className="text-ink-muted">Delivery</dt>
                <dd className="tabular-nums">
                  {Number(order.shipping_amount) === 0
                    ? "Free"
                    : formatPrice(order.shipping_amount)}
                </dd>
              </div>
              <div className="flex items-baseline justify-between border-t border-line pt-2">
                <dt className="font-semibold text-ink">Total</dt>
                <dd className="font-display text-xl">{formatPrice(order.total_amount)}</dd>
              </div>
            </dl>
          </section>

          {/* Returns */}
          {order.return_requests.length > 0 ? (
            <section className="mt-10">
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
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {canRequestReturn ? (
            <section className="mt-8 border border-line bg-gold-wash p-6">
              {showReturnForm ? (
                <ReturnRequestForm
                  orderNumber={order.order_number}
                  onDone={(updated) => {
                    setShowReturnForm(false);
                    if (updated) void getMyOrder(order.order_number).then(setOrder);
                  }}
                />
              ) : (
                <>
                  <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
                    Not right?
                  </h2>
                  <p className="mt-2 text-sm text-ink-muted">
                    You can request a return or an exchange on a delivered order.
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="mt-4"
                    onClick={() => setShowReturnForm(true)}
                  >
                    <RotateCcw className="size-3.5" aria-hidden />
                    Request return or exchange
                  </Button>
                </>
              )}
            </section>
          ) : null}
        </div>

        {/* Sidebar */}
        <aside className="mt-10 space-y-4 lg:mt-0">
          <section className="border border-line bg-surface p-5">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Order progress
            </h2>
            <div className="mt-4">
              <OrderTimeline status={order.order_status} events={order.status_events} />
            </div>
          </section>

          {/* Shipping status is shown separately from order progress above,
              because the two advance independently. */}
          <ShipmentPanel shipment={order.shipment} />

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
              {order.shipping_address_snapshot.country}
              <br />
              {order.shipping_address_snapshot.phone}
            </address>
          </section>

          <section className="border border-line bg-surface p-5">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Payment
            </h2>
            <p className="mt-3 text-sm text-ink">
              {PAYMENT_METHOD_LABELS[order.payment_method]}
            </p>
            <div className="mt-2">
              <PaymentStatusPill status={order.payment_status} />
            </div>

            {/* Bank transfer: the customer reports their reference, staff verify
                it. Submitting never marks the payment paid. */}
            {order.payment_method === "BANK_TRANSFER" &&
            order.payment_status === "PENDING" ? (
              <BankTransferForm
                orderNumber={order.order_number}
                submittedReference={order.payment?.customer_reference ?? null}
                onSubmitted={() => setReloadKey((key) => key + 1)}
              />
            ) : null}

            {order.payment?.failure_reason ? (
              <p className="mt-3 border-l-2 border-danger bg-danger/5 px-3 py-2 text-xs text-danger">
                {order.payment.failure_reason}
              </p>
            ) : null}
            {order.customer_note ? (
              <>
                <h3 className="mt-5 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
                  Your note
                </h3>
                <p className="mt-2 text-sm text-ink-muted">{order.customer_note}</p>
              </>
            ) : null}
          </section>

          {order.is_cancellable_by_customer ? (
            <Button
              variant="secondary"
              className="w-full"
              onClick={handleCancel}
              disabled={busy}
            >
              {busy ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <XCircle className="size-4" aria-hidden />
              )}
              Cancel order
            </Button>
          ) : order.order_status === "CANCELLED" ? null : (
            <p className="text-xs leading-relaxed text-stone">
              This order is already on its way, so it can no longer be cancelled here. Contact us
              or open a return once it arrives.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}

function ReturnRequestForm({
  orderNumber,
  onDone,
}: {
  orderNumber: string;
  onDone: (updated: boolean) => void;
}) {
  const [type, setType] = useState<ReturnRequestType>("RETURN");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await requestReturn(orderNumber, {
        type,
        reason: String(form.get("reason")),
        description: String(form.get("description") ?? "") || undefined,
      });
      onDone(true);
    } catch (caught) {
      setError(errorMessage(caught, "Could not submit that request."));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
        Return or exchange
      </h2>

      <div className="flex gap-2">
        {(["RETURN", "EXCHANGE"] as ReturnRequestType[]).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setType(option)}
            aria-pressed={type === option}
            className={
              type === option
                ? "border border-ink bg-ink px-4 py-2 text-xs font-semibold uppercase tracking-[0.1em] text-paper"
                : "border border-line-strong px-4 py-2 text-xs font-semibold uppercase tracking-[0.1em] text-ink hover:border-ink"
            }
          >
            {option === "RETURN" ? "Return" : "Exchange"}
          </button>
        ))}
      </div>

      <label className="block">
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
          Reason
        </span>
        <input
          name="reason"
          required
          minLength={3}
          maxLength={160}
          placeholder="Does not fit, not as described…"
          className="mt-1.5 h-11 w-full border border-line bg-surface px-3 text-sm outline-none focus:border-gold"
        />
      </label>

      <label className="block">
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
          Details (optional)
        </span>
        <textarea
          name="description"
          rows={3}
          maxLength={2000}
          className="mt-1.5 w-full border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-gold"
        />
      </label>

      {error ? (
        <p role="alert" className="border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
          {error}
        </p>
      ) : null}

      <p className="text-xs text-stone">
        Our team will review your request and get in touch. Collection and refunds are arranged
        manually for now.
      </p>

      <div className="flex gap-2.5">
        <Button type="submit" size="sm" disabled={busy}>
          {busy ? "Submitting…" : "Submit request"}
        </Button>
        <Button type="button" variant="secondary" size="sm" onClick={() => onDone(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
