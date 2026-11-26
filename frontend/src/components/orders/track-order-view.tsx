"use client";

/**
 * Public order tracker.
 *
 * Requires the order number *and* a matching contact detail, because an order
 * number alone must never reveal where someone's parcel is going. The response
 * carries no address, no prices, and no customer name.
 */

import { useState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ShipmentHistory,
  ShippingProgress,
  ShippingStatusPill,
} from "@/components/orders/shipping-status";
import { ORDER_STATUS_LABELS } from "@/components/orders/order-status";
import { trackOrder } from "@/lib/api/payments";
import { formatDateTime } from "@/lib/format";
import type { CourierProvider, TrackingResult } from "@/lib/api/types";

const COURIER_LABELS: Record<CourierProvider, string> = {
  MANUAL: "Courier",
  TCS: "TCS",
  LEOPARDS: "Leopards Courier",
  MP: "M&P",
  TRAX: "Trax",
  POSTEX: "PostEx",
};

const FIELD =
  "w-full border border-line bg-surface px-3 py-2.5 text-sm text-ink outline-none transition-colors placeholder:text-stone focus:border-gold";

export function TrackOrderView() {
  const [orderNumber, setOrderNumber] = useState("");
  const [contact, setContact] = useState("");
  const [result, setResult] = useState<TrackingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await trackOrder(orderNumber.trim(), contact.trim()));
    } catch (cause) {
      setResult(null);
      setError(
        cause instanceof Error
          ? cause.message
          : "We could not find that order. Please check the details and try again."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <form onSubmit={handleSubmit} className="border border-line bg-surface p-5 sm:p-7">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs uppercase tracking-[0.12em] text-stone">
              Order number
            </span>
            <input
              value={orderNumber}
              onChange={(event) => setOrderNumber(event.target.value)}
              placeholder="RG-20260812-0001"
              required
              minLength={4}
              autoComplete="off"
              className={`${FIELD} font-mono`}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs uppercase tracking-[0.12em] text-stone">
              Email or phone
            </span>
            <input
              value={contact}
              onChange={(event) => setContact(event.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="off"
              className={FIELD}
            />
          </label>
        </div>
        <p className="mt-3 text-xs text-stone">
          We ask for both so nobody else can look up your delivery.
        </p>
        <div className="mt-5">
          <Button type="submit" disabled={busy}>
            {busy ? "Looking…" : "Track order"}
          </Button>
        </div>
      </form>

      {error ? (
        <p
          role="alert"
          className="mt-5 border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        >
          {error}
        </p>
      ) : null}

      {result ? <TrackingResultPanel result={result} /> : null}
    </div>
  );
}

function TrackingResultPanel({ result }: { result: TrackingResult }) {
  return (
    <section className="mt-6 border border-line bg-surface p-5 sm:p-7">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.12em] text-stone">Order</p>
          <p className="font-mono text-lg text-ink">{result.order_number}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone="neutral">{ORDER_STATUS_LABELS[result.order_status]}</Badge>
          {result.shipping_status ? (
            <ShippingStatusPill status={result.shipping_status} />
          ) : null}
        </div>
      </div>

      {result.shipping_status ? (
        <div className="mt-6">
          <ShippingProgress status={result.shipping_status} />
        </div>
      ) : null}

      <dl className="mt-6 grid gap-x-8 gap-y-3 border-t border-line pt-5 text-sm sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <dt className="text-xs uppercase tracking-[0.12em] text-stone">Placed</dt>
          <dd className="text-ink">{formatDateTime(result.placed_at)}</dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className="text-xs uppercase tracking-[0.12em] text-stone">Items</dt>
          <dd className="text-ink">
            {result.item_count} {result.item_count === 1 ? "piece" : "pieces"}
          </dd>
        </div>
        {result.tracking_number ? (
          <div className="flex flex-col gap-1">
            <dt className="text-xs uppercase tracking-[0.12em] text-stone">
              Tracking number
            </dt>
            <dd>
              {result.tracking_url ? (
                <a
                  href={result.tracking_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-ink underline decoration-gold/60 underline-offset-4"
                >
                  {result.tracking_number}
                </a>
              ) : (
                <span className="font-mono text-ink">{result.tracking_number}</span>
              )}
            </dd>
          </div>
        ) : null}
        {result.courier && result.tracking_number ? (
          <div className="flex flex-col gap-1">
            <dt className="text-xs uppercase tracking-[0.12em] text-stone">Courier</dt>
            <dd className="text-ink">{COURIER_LABELS[result.courier]}</dd>
          </div>
        ) : null}
      </dl>

      <ul className="mt-5 space-y-2 border-t border-line pt-5 text-sm">
        {result.items.map((item, index) => (
          <li key={`${item.name}-${index}`} className="flex justify-between gap-4">
            <span className="min-w-0 text-ink">
              {item.name}
              <span className="text-stone"> · {item.variant_label}</span>
            </span>
            <span className="shrink-0 text-ink-muted">×{item.quantity}</span>
          </li>
        ))}
      </ul>

      {result.status_history.length > 0 ? (
        <ShipmentHistory events={result.status_history} />
      ) : null}

      <p className="mt-6 border-t border-line pt-5 text-sm text-ink-muted">
        Signed in?{" "}
        <Link
          href="/account/orders"
          className="text-ink underline decoration-gold/60 underline-offset-4"
        >
          See full order details
        </Link>
        .
      </p>
    </section>
  );
}
