"use client";

/**
 * Courier and shipping controls on the admin order page.
 *
 * With no courier API connected, this is the real workflow: staff book the
 * consignment in the courier's own portal and record the number here. The form
 * says so plainly rather than implying the system booked anything.
 */

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  SHIPPING_LABELS,
  ShippingStatusPill,
} from "@/components/orders/shipping-status";
import {
  assignCourier,
  listCouriers,
  shippingLabelUrl,
  updateShippingStatus,
} from "@/lib/api/payments";
import { formatDateTime } from "@/lib/format";
import type {
  CourierProvider,
  CourierStatus,
  Shipment,
  ShippingStatus,
} from "@/lib/api/types";

/** Mirrors the backend transition table so the UI only offers legal moves. */
const NEXT_STATUSES: Record<ShippingStatus, ShippingStatus[]> = {
  PENDING: ["READY", "CANCELLED"],
  READY: ["DISPATCHED", "CANCELLED"],
  DISPATCHED: ["IN_TRANSIT", "RETURNED"],
  IN_TRANSIT: ["OUT_FOR_DELIVERY", "DELIVERED", "RETURNED"],
  OUT_FOR_DELIVERY: ["DELIVERED", "RETURNED"],
  DELIVERED: ["RETURNED"],
  RETURNED: [],
  CANCELLED: [],
};

const FIELD =
  "w-full border border-line bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-stone focus:border-gold";

export function AdminShippingPanel({
  orderId,
  shipment: initial,
  onChange,
}: {
  orderId: string;
  shipment: Shipment | null;
  onChange?: (shipment: Shipment) => void;
}) {
  const [shipment, setShipment] = useState<Shipment | null>(initial);
  const [couriers, setCouriers] = useState<CourierStatus[]>([]);
  const [provider, setProvider] = useState<CourierProvider>(
    initial?.provider ?? "MANUAL"
  );
  const [trackingNumber, setTrackingNumber] = useState(
    initial?.tracking_number ?? ""
  );
  const [trackingUrl, setTrackingUrl] = useState(initial?.tracking_url ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [statusNote, setStatusNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCouriers().then(setCouriers).catch(() => setCouriers([]));
  }, []);

  function apply(next: Shipment) {
    setShipment(next);
    setProvider(next.provider);
    setTrackingNumber(next.tracking_number ?? "");
    setTrackingUrl(next.tracking_url ?? "");
    setNotes(next.notes ?? "");
    setStatusNote("");
    onChange?.(next);
  }

  async function run(action: () => Promise<Shipment>) {
    setBusy(true);
    setError(null);
    try {
      apply(await action());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That action failed.");
    } finally {
      setBusy(false);
    }
  }

  const currentStatus = shipment?.shipping_status ?? "PENDING";
  const allowedNext = NEXT_STATUSES[currentStatus];
  const selectedCourier = couriers.find((entry) => entry.code === provider);

  return (
    <section className="border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
        <h2 className="font-serif text-lg text-ink">Shipping</h2>
        <ShippingStatusPill status={currentStatus} />
      </div>

      <div className="space-y-5 p-5">
        {shipment ? (
          <a className="inline-flex border border-line px-3 py-2 text-sm text-ink hover:border-gold" href={shippingLabelUrl(orderId)} target="_blank" rel="noreferrer">
            Print shipping label
          </a>
        ) : null}
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs uppercase tracking-[0.12em] text-stone">
              Courier
            </span>
            <select
              value={provider}
              onChange={(event) =>
                setProvider(event.target.value as CourierProvider)
              }
              className={FIELD}
            >
              {couriers.map((courier) => (
                <option key={courier.code} value={courier.code}>
                  {courier.display_name}
                  {courier.is_automated ? "" : " (manual)"}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs uppercase tracking-[0.12em] text-stone">
              Tracking number
            </span>
            <input
              value={trackingNumber}
              onChange={(event) => setTrackingNumber(event.target.value)}
              placeholder="From the courier's portal"
              className={`${FIELD} font-mono`}
            />
          </label>

          <label className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-xs uppercase tracking-[0.12em] text-stone">
              Tracking URL <span className="normal-case text-stone">(optional)</span>
            </span>
            <input
              value={trackingUrl}
              onChange={(event) => setTrackingUrl(event.target.value)}
              placeholder="https://courier.example/track/…"
              className={FIELD}
            />
          </label>

          <label className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-xs uppercase tracking-[0.12em] text-stone">
              Internal notes
            </span>
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={2}
              className={FIELD}
            />
          </label>
        </div>

        {selectedCourier && !selectedCourier.is_configured ? (
          <p className="border-l-2 border-gold bg-gold/5 px-3 py-2 text-xs text-ink-muted">
            {selectedCourier.configuration_hint}
          </p>
        ) : null}

        <Button
          disabled={busy}
          onClick={() =>
            run(() =>
              assignCourier(orderId, {
                provider,
                tracking_number: trackingNumber.trim() || null,
                tracking_url: trackingUrl.trim() || null,
                notes: notes.trim() || null,
              })
            )
          }
        >
          {busy ? "Saving…" : "Save courier details"}
        </Button>

        <div className="border-t border-line pt-5">
          <p className="text-xs uppercase tracking-[0.12em] text-stone">
            Advance shipping status
          </p>
          {allowedNext.length === 0 ? (
            <p className="mt-2 text-sm text-ink-muted">
              {SHIPPING_LABELS[currentStatus]} is a final state.
            </p>
          ) : (
            <>
              <input
                value={statusNote}
                onChange={(event) => setStatusNote(event.target.value)}
                placeholder="Note for this update (optional)"
                className={`${FIELD} mt-2`}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                {allowedNext.map((status) => (
                  <Button
                    key={status}
                    variant="secondary"
                    disabled={busy}
                    onClick={() =>
                      run(() =>
                        updateShippingStatus(
                          orderId,
                          status,
                          statusNote.trim() || undefined
                        )
                      )
                    }
                  >
                    {SHIPPING_LABELS[status]}
                  </Button>
                ))}
              </div>
              {!shipment?.tracking_number ? (
                <p className="mt-3 text-xs text-stone">
                  A tracking number is required before a parcel can be marked
                  dispatched.
                </p>
              ) : null}
            </>
          )}
        </div>

        {shipment && shipment.events.length > 0 ? (
          <div className="border-t border-line pt-5">
            <p className="text-xs uppercase tracking-[0.12em] text-stone">History</p>
            <ol className="mt-3 space-y-2 text-sm">
              {[...shipment.events].reverse().map((event) => (
                <li key={event.id} className="flex flex-wrap items-baseline gap-2">
                  <Badge tone="neutral">{SHIPPING_LABELS[event.status]}</Badge>
                  <span className="text-xs text-stone">
                    {formatDateTime(event.created_at)}
                  </span>
                  {event.note ? (
                    <span className="text-ink-muted">{event.note}</span>
                  ) : null}
                </li>
              ))}
            </ol>
          </div>
        ) : null}
      </div>
    </section>
  );
}
