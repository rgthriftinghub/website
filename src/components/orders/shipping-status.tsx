/**
 * Shipping status display, shared by the customer order page and the tracker.
 *
 * Deliberately separate from the order timeline: order status and shipping status
 * are different things moving on different clocks, and collapsing them into one
 * progress bar would misrepresent both.
 */

import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CourierProvider, Shipment, ShipmentEvent, ShippingStatus } from "@/lib/api/types";

export const SHIPPING_LABELS: Record<ShippingStatus, string> = {
  PENDING: "Preparing",
  READY: "Ready to ship",
  DISPATCHED: "Dispatched",
  IN_TRANSIT: "In transit",
  OUT_FOR_DELIVERY: "Out for delivery",
  DELIVERED: "Delivered",
  RETURNED: "Returned",
  CANCELLED: "Cancelled",
};

export const COURIER_LABELS: Record<CourierProvider, string> = {
  MANUAL: "Courier",
  TCS: "TCS",
  LEOPARDS: "Leopards Courier",
  MP: "M&P",
  TRAX: "Trax",
  POSTEX: "PostEx",
};

/** The forward path a parcel takes. Returns and cancellations branch off it. */
export const SHIPPING_STEPS: ShippingStatus[] = [
  "PENDING",
  "READY",
  "DISPATCHED",
  "IN_TRANSIT",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
];

const TERMINAL_BAD: ShippingStatus[] = ["RETURNED", "CANCELLED"];

const STATUS_TONES: Record<ShippingStatus, string> = {
  PENDING: "bg-paper-alt text-ink-muted",
  READY: "bg-gold-wash text-gold-deep",
  DISPATCHED: "bg-paper-alt text-ink",
  IN_TRANSIT: "bg-paper-alt text-ink",
  OUT_FOR_DELIVERY: "bg-gold-wash text-gold-deep",
  DELIVERED: "bg-success/12 text-success",
  RETURNED: "bg-danger/10 text-danger",
  CANCELLED: "bg-danger/10 text-danger",
};

export function ShippingStatusPill({
  status,
  className,
}: {
  status: ShippingStatus;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
        STATUS_TONES[status],
        className
      )}
    >
      {SHIPPING_LABELS[status]}
    </span>
  );
}

/**
 * Horizontal step rail. Terminal bad states fall back to a single line, because a
 * half-filled rail on a returned parcel reads as "still on its way".
 */
export function ShippingProgress({ status }: { status: ShippingStatus }) {
  if (TERMINAL_BAD.includes(status)) {
    return (
      <div className="flex items-center gap-2.5">
        <span className="size-1.5 rounded-full bg-danger" aria-hidden />
        <p className="text-sm font-medium text-danger">{SHIPPING_LABELS[status]}</p>
      </div>
    );
  }

  const currentIndex = SHIPPING_STEPS.indexOf(status);

  return (
    <ol className="flex flex-wrap gap-x-1.5 gap-y-3" aria-label="Shipping progress">
      {SHIPPING_STEPS.map((step, index) => {
        const reached = index <= currentIndex;
        const isCurrent = index === currentIndex;
        return (
          <li key={step} className="flex min-w-0 flex-1 basis-20 flex-col gap-2">
            <span
              className={cn("h-[3px] w-full rounded-full", reached ? "bg-gold" : "bg-line")}
              aria-hidden
            />
            <span
              className={cn(
                "text-[11px] leading-tight",
                isCurrent
                  ? "font-semibold text-ink"
                  : reached
                    ? "text-ink-muted"
                    : "text-stone"
              )}
            >
              {SHIPPING_LABELS[step]}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function TrackingNumber({ shipment }: { shipment: Shipment }) {
  if (!shipment.tracking_number) return null;
  if (!shipment.tracking_url) {
    return (
      <span className="font-mono text-sm text-ink">{shipment.tracking_number}</span>
    );
  }
  return (
    <a
      href={shipment.tracking_url}
      target="_blank"
      rel="noopener noreferrer"
      className="font-mono text-sm text-ink underline decoration-gold/60 underline-offset-4 transition-colors hover:decoration-gold"
    >
      {shipment.tracking_number}
    </a>
  );
}

/** Customer-facing delivery panel. */
export function ShipmentPanel({ shipment }: { shipment: Shipment | null }) {
  if (!shipment) return null;

  return (
    <section className="border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
          Delivery
        </h2>
        <ShippingStatusPill status={shipment.shipping_status} />
      </div>

      <div className="mt-5">
        <ShippingProgress status={shipment.shipping_status} />
      </div>

      {shipment.tracking_number ? (
        <dl className="mt-6 grid gap-x-8 gap-y-3 border-t border-line pt-5 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-[0.12em] text-stone">
              Tracking number
            </dt>
            <dd className="mt-1">
              <TrackingNumber shipment={shipment} />
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-[0.12em] text-stone">Courier</dt>
            <dd className="mt-1 text-ink">{COURIER_LABELS[shipment.provider]}</dd>
          </div>
          {shipment.shipped_at ? (
            <div>
              <dt className="text-xs uppercase tracking-[0.12em] text-stone">
                Dispatched
              </dt>
              <dd className="mt-1 text-ink-muted">
                {formatDateTime(shipment.shipped_at)}
              </dd>
            </div>
          ) : null}
          {shipment.delivered_at ? (
            <div>
              <dt className="text-xs uppercase tracking-[0.12em] text-stone">
                Delivered
              </dt>
              <dd className="mt-1 text-ink-muted">
                {formatDateTime(shipment.delivered_at)}
              </dd>
            </div>
          ) : null}
        </dl>
      ) : (
        <p className="mt-5 border-t border-line pt-4 text-sm text-ink-muted">
          A tracking number will appear here once your parcel has been handed to the
          courier.
        </p>
      )}

      {shipment.events.length > 0 ? <ShipmentHistory events={shipment.events} /> : null}
    </section>
  );
}

export function ShipmentHistory({ events }: { events: ShipmentEvent[] }) {
  const newestFirst = [...events].reverse();
  return (
    <div className="mt-6 border-t border-line pt-5">
      <h3 className="text-xs uppercase tracking-[0.12em] text-stone">History</h3>
      <ol className="mt-3 space-y-3">
        {newestFirst.map((event) => (
          <li key={event.id} className="flex gap-3 text-sm">
            <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-gold" aria-hidden />
            <div className="min-w-0">
              <p className="text-ink">{SHIPPING_LABELS[event.status]}</p>
              {event.note ? <p className="text-ink-muted">{event.note}</p> : null}
              <p className="text-xs text-stone">
                {formatDateTime(event.created_at)}
                {event.location ? ` · ${event.location}` : ""}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
