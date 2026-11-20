import { Ban, Check, PackageCheck, RotateCcw, Truck } from "lucide-react";

import type { OrderStatus, PaymentMethod, PaymentStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  PENDING: "Order Placed",
  PROCESSING: "Processing",
  PACKED: "Packed",
  DISPATCHED: "Dispatched",
  DELIVERED: "Delivered",
  CANCELLED: "Cancelled",
  RETURNED: "Returned",
  EXCHANGE: "Exchanged",
};

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  COD: "Cash on Delivery",
  BANK_TRANSFER: "Bank Transfer",
  JAZZCASH: "JazzCash",
  EASYPAISA: "Easypaisa",
  PAYFAST: "PayFast",
  SAFEPAY: "Safepay",
};

/** The forward path an order takes; cancellation and returns branch off it. */
export const FULFILMENT_STEPS: OrderStatus[] = [
  "PENDING",
  "PROCESSING",
  "PACKED",
  "DISPATCHED",
  "DELIVERED",
];

const STATUS_TONES: Record<OrderStatus, string> = {
  PENDING: "bg-gold-wash text-gold-deep",
  PROCESSING: "bg-gold-wash text-gold-deep",
  PACKED: "bg-paper-alt text-ink",
  DISPATCHED: "bg-paper-alt text-ink",
  DELIVERED: "bg-success/12 text-success",
  CANCELLED: "bg-danger/10 text-danger",
  RETURNED: "bg-line text-ink-muted",
  EXCHANGE: "bg-line text-ink-muted",
};

export function OrderStatusPill({
  status,
  className,
}: {
  status: OrderStatus;
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
      {ORDER_STATUS_LABELS[status]}
    </span>
  );
}

export function PaymentStatusPill({ status }: { status: PaymentStatus }) {
  const tone =
    status === "PAID"
      ? "success"
      : status === "FAILED"
        ? "danger"
        : status === "REFUNDED"
          ? "muted"
          : "pending";

  const classes = {
    success: "bg-success/12 text-success",
    danger: "bg-danger/10 text-danger",
    muted: "bg-line text-ink-muted",
    pending: "bg-paper-alt text-ink-muted",
  }[tone];

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
        classes
      )}
    >
      {status === "PENDING" ? "Payment Pending" : status.toLowerCase()}
    </span>
  );
}

const STEP_ICONS: Partial<Record<OrderStatus, typeof Check>> = {
  PACKED: PackageCheck,
  DISPATCHED: Truck,
  DELIVERED: Check,
  CANCELLED: Ban,
  RETURNED: RotateCcw,
  EXCHANGE: RotateCcw,
};

/**
 * Vertical fulfilment timeline.
 *
 * A cancelled order shows the steps it actually reached and then Cancelled,
 * rather than pretending the remaining steps are still pending.
 */
export function OrderTimeline({
  status,
  events,
}: {
  status: OrderStatus;
  events: { status: OrderStatus; note: string | null; created_at: string }[];
}) {
  const reached = new Set(events.map((event) => event.status));
  const terminal: OrderStatus[] = ["CANCELLED", "RETURNED", "EXCHANGE"];
  const isTerminal = terminal.includes(status);

  const steps: OrderStatus[] = isTerminal
    ? [...FULFILMENT_STEPS.filter((step) => reached.has(step)), status]
    : FULFILMENT_STEPS;

  const currentIndex = steps.indexOf(status);

  const timestampFor = (step: OrderStatus) =>
    events.find((event) => event.status === step)?.created_at ?? null;
  const noteFor = (step: OrderStatus) =>
    events.filter((event) => event.status === step).at(-1)?.note ?? null;

  return (
    <ol className="relative">
      {steps.map((step, index) => {
        const done = index <= currentIndex;
        const isCurrent = index === currentIndex;
        const isBad = terminal.includes(step);
        const Icon = STEP_ICONS[step] ?? Check;
        const timestamp = timestampFor(step);
        const note = noteFor(step);

        return (
          <li key={step} className="relative flex gap-4 pb-6 last:pb-0">
            {index < steps.length - 1 ? (
              <span
                aria-hidden
                className={cn(
                  "absolute left-[13px] top-7 h-[calc(100%-1.75rem)] w-px",
                  done && !isBad ? "bg-gold" : "bg-line"
                )}
              />
            ) : null}

            <span
              className={cn(
                "relative z-10 grid size-7 shrink-0 place-items-center rounded-full border",
                isBad && done
                  ? "border-danger bg-danger text-paper"
                  : done
                    ? "border-gold bg-gold text-ink"
                    : "border-line bg-paper text-line-strong"
              )}
            >
              <Icon className="size-3.5" aria-hidden />
            </span>

            <div className="min-w-0 pt-0.5">
              <p
                className={cn(
                  "text-sm",
                  isCurrent ? "font-semibold text-ink" : done ? "text-ink" : "text-stone"
                )}
              >
                {ORDER_STATUS_LABELS[step]}
              </p>
              {timestamp ? (
                <p className="mt-0.5 text-xs text-stone">
                  {new Date(timestamp).toLocaleString("en-PK", {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })}
                </p>
              ) : null}
              {note ? <p className="mt-1 text-xs text-ink-muted">{note}</p> : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
