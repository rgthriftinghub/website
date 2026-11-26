"use client";

import Link from "next/link";
import { Check, FileText, Package, Truck } from "lucide-react";
import { useEffect, useState } from "react";

import { PAYMENT_METHOD_LABELS } from "@/components/orders/order-status";
import { ButtonLink } from "@/components/ui/button";
import { getCheckoutConfig, getMyOrder, myInvoiceUrl } from "@/lib/api/commerce";
import type { CheckoutConfig, Order } from "@/lib/api/types";
import { formatPrice } from "@/lib/format";

const PAYMENT_INSTRUCTIONS: Record<string, string> = {
  COD: "Please have the exact amount ready for the courier when your parcel arrives.",
  BANK_TRANSFER:
    "Our team will contact you with bank details. Quote your order number with the transfer so we can match it quickly.",
};

export function OrderSuccessView({ orderNumber }: { orderNumber: string }) {
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkoutConfig, setCheckoutConfig] = useState<CheckoutConfig | null>(null);

  useEffect(() => {
    void getCheckoutConfig().then(setCheckoutConfig).catch(() => undefined);
    getMyOrder(orderNumber)
      .then(setOrder)
      .catch(() => setError("We could not find that order on your account."));
  }, [orderNumber]);

  if (error) {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <h1 className="font-display text-3xl">Order not found</h1>
        <p className="mt-3 text-sm text-ink-muted">{error}</p>
        <ButtonLink href="/account/orders" className="mt-8">
          View your orders
        </ButtonLink>
      </div>
    );
  }

  if (order === null) {
    return (
      <div className="grid place-items-center py-28">
        <p className="text-sm text-stone" role="status">
          Loading your confirmation…
        </p>
      </div>
    );
  }

  const isShipped = ["DISPATCHED", "DELIVERED"].includes(order.order_status);
  const isConfirmed =
    isShipped ||
    order.payment_status === "PAID" ||
    ["PROCESSING", "PACKED"].includes(order.order_status);

  return (
    <div className="mx-auto max-w-3xl px-4 py-14 sm:px-6 lg:py-20">
      <div className="text-center">
        <span className="mx-auto grid size-16 place-items-center rounded-full bg-gold">
          <Check className="size-7 text-ink" aria-hidden />
        </span>
        {!isConfirmed ? <p className="eyebrow mt-6">Thank you</p> : null}
        <h1 className="mt-2 text-4xl sm:text-5xl">
          {isShipped
            ? "Your order has been shipped"
            : isConfirmed
              ? "Your order is confirmed"
              : "Your order has been received"}
        </h1>
        {!isConfirmed ? (
          <p className="mx-auto mt-4 max-w-lg text-sm text-ink-muted">
            Our team will confirm your order after verifying your payment. Keep your order number
            handy and send your payment receipt on WhatsApp if you paid by JazzCash or Easypaisa.
          </p>
        ) : null}
      </div>

      <div className="mt-10 border border-line bg-surface">
        <dl className="grid grid-cols-2 divide-line sm:grid-cols-4 sm:divide-x">
          {[
            { label: "Order number", value: order.order_number, mono: true },
            { label: "Total", value: formatPrice(order.total_amount) },
            { label: "Payment", value: PAYMENT_METHOD_LABELS[order.payment_method] },
            {
              label: "Placed",
              value: new Date(order.created_at).toLocaleDateString("en-PK", {
                dateStyle: "medium",
              }),
            },
          ].map((entry) => (
            <div key={entry.label} className="border-b border-line p-5 last:border-b-0 sm:border-b-0">
              <dt className="text-[10px] font-semibold uppercase tracking-[0.12em] text-stone">
                {entry.label}
              </dt>
              <dd
                className={
                  entry.mono
                    ? "mt-1.5 font-mono text-sm font-semibold text-ink"
                    : "mt-1.5 text-sm font-semibold text-ink"
                }
              >
                {entry.value}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <section className="border border-line bg-surface p-6">
          <h2 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
            <Truck className="size-3.5 text-gold-deep" aria-hidden />
            Delivery
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
          <p className="mt-3 text-xs text-stone">
            Standard delivery, typically 3–5 working days.
          </p>
        </section>

        <section className="border border-line bg-gold-wash p-6">
          <h2 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
            <Package className="size-3.5 text-gold-deep" aria-hidden />
            What happens next
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-ink-muted">
            {order.payment_method === "JAZZCASH"
              ? `Send ${formatPrice(order.total_amount)} to JazzCash ${checkoutConfig?.jazzcash_number ?? ""}, then send your payment receipt on WhatsApp. Our team will confirm your order manually after verifying the payment.`
              : order.payment_method === "EASYPAISA"
                ? `Send ${formatPrice(order.total_amount)} to Easypaisa ${checkoutConfig?.easypaisa_number ?? ""}, then send your payment receipt on WhatsApp. Our team will confirm your order manually after verifying the payment.`
                : PAYMENT_INSTRUCTIONS[order.payment_method] ?? ""}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            You can follow progress on your order page at any time.
          </p>
        </section>
      </div>

      <ul className="mt-4 divide-y divide-line border border-line bg-surface">
        {order.items.map((item) => (
          <li key={item.id} className="flex items-center justify-between gap-4 p-4 text-sm">
            <div className="min-w-0">
              <p className="truncate text-ink">{item.product_name_snapshot}</p>
              <p className="text-xs text-stone">
                {item.variant_label} · Qty {item.quantity}
              </p>
            </div>
            <span className="shrink-0 tabular-nums text-ink">{formatPrice(item.line_total)}</span>
          </li>
        ))}
      </ul>

      <div className="mt-8 flex flex-wrap justify-center gap-2.5">
        <ButtonLink href={`/account/orders/${order.order_number}`} size="lg">
          View order
        </ButtonLink>
        <ButtonLink href="/shop" variant="secondary" size="lg">
          Continue shopping
        </ButtonLink>
      </div>

      {(order.payment_method === "JAZZCASH" || order.payment_method === "EASYPAISA") && checkoutConfig?.payment_whatsapp_number ? (
        <div className="mt-6 text-center">
          <a
            href={`https://wa.me/${checkoutConfig.payment_whatsapp_number.replace(/\D/g, "")}?text=${encodeURIComponent(`Assalam-o-Alaikum, I have paid for order ${order.order_number} via ${order.payment_method === "JAZZCASH" ? "JazzCash" : "Easypaisa"}. I am sending my payment screenshot for confirmation.`)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center justify-center bg-[#25D366] px-6 text-sm font-semibold text-white hover:bg-[#1fb958]"
          >
            Send Payment Receipt on WhatsApp
          </a>
        </div>
      ) : null}

      <div className="mt-6 text-center">
        <Link
          href={myInvoiceUrl(order.order_number)}
          target="_blank"
          rel="noopener"
          className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-gold-deep hover:text-ink"
        >
          <FileText className="size-3.5" aria-hidden />
          Download invoice
        </Link>
      </div>
    </div>
  );
}
