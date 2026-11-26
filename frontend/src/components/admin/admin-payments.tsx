"use client";

/**
 * Admin payment management.
 *
 * Information-dense by design. The only mutating actions offered are the audited
 * ones the backend allows: verify or reject a bank transfer, record COD
 * collection, and record a refund. There is deliberately no way to hand-edit a
 * gateway payment's status.
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  getAdminPaymentStats,
  listAdminPayments,
  listPaymentProviders,
  markCodCollected,
  rejectBankTransfer,
  verifyBankTransfer,
} from "@/lib/api/payments";
import { formatDateTime, formatPrice } from "@/lib/format";
import type {
  AdminPayment,
  PaymentMethod,
  PaymentProviderStatus,
  PaymentQuery,
  PaymentStats,
  PaymentStatus,
} from "@/lib/api/types";

const STATUS_TONES: Record<PaymentStatus, "neutral" | "sale" | "new"> = {
  PENDING: "neutral",
  PROCESSING: "neutral",
  PAID: "new",
  FAILED: "sale",
  CANCELLED: "sale",
  REFUNDED: "sale",
};

const METHOD_LABELS: Record<PaymentMethod, string> = {
  COD: "Cash on Delivery",
  BANK_TRANSFER: "Bank Transfer",
  PAYFAST: "PayFast",
  SAFEPAY: "Safepay",
  JAZZCASH: "JazzCash",
  EASYPAISA: "Easypaisa",
};

const STATUSES: PaymentStatus[] = [
  "PENDING",
  "PROCESSING",
  "PAID",
  "FAILED",
  "CANCELLED",
  "REFUNDED",
];

const SELECT =
  "border border-line bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-gold";

export function AdminPayments() {
  // null means "not loaded yet", so loading is derived rather than tracked in a
  // separate flag that an effect would have to set synchronously.
  const [payments, setPayments] = useState<AdminPayment[] | null>(null);
  const [stats, setStats] = useState<PaymentStats | null>(null);
  const [providers, setProviders] = useState<PaymentProviderStatus[]>([]);
  const [query, setQuery] = useState<PaymentQuery>({ page: 1, page_size: 25 });
  const [total, setTotal] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listAdminPayments(query), getAdminPaymentStats()])
      .then(([page, statsResult]) => {
        if (cancelled) return;
        setPayments(page.items);
        setTotal(page.total);
        setStats(statsResult);
      })
      .catch((cause) => {
        if (cancelled) return;
        setPayments([]);
        setError(cause instanceof Error ? cause.message : "Could not load payments.");
      });
    return () => {
      cancelled = true;
    };
  }, [query, reloadKey]);

  useEffect(() => {
    // Provider state is static per deployment, so it is fetched once.
    listPaymentProviders().then(setProviders).catch(() => setProviders([]));
  }, []);

  async function act(id: string, action: () => Promise<unknown>) {
    setBusyId(id);
    setError(null);
    try {
      await action();
      setReloadKey((key) => key + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That action failed.");
    } finally {
      setBusyId(null);
    }
  }

  const loading = payments === null;

  const patch = (changes: Partial<PaymentQuery>) =>
    setQuery((current) => ({ ...current, ...changes, page: 1 }));

  return (
    <div className="space-y-8">
      <PaymentStatsRow stats={stats} />
      <ProviderNotice providers={providers} />

      <section className="border border-line bg-surface">
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
          <input
            defaultValue={query.search ?? ""}
            onChange={(event) => patch({ search: event.target.value || undefined })}
            placeholder="Order number, reference, transaction id"
            className={`${SELECT} min-w-[16rem] flex-1`}
            aria-label="Search payments"
          />
          <select
            value={query.status ?? ""}
            onChange={(event) =>
              patch({ status: (event.target.value || undefined) as PaymentStatus })
            }
            className={SELECT}
            aria-label="Filter by payment status"
          >
            <option value="">All statuses</option>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
          <select
            value={query.payment_method ?? ""}
            onChange={(event) =>
              patch({
                payment_method: (event.target.value || undefined) as PaymentMethod,
              })
            }
            className={SELECT}
            aria-label="Filter by method"
          >
            <option value="">All methods</option>
            {(Object.keys(METHOD_LABELS) as PaymentMethod[]).map((method) => (
              <option key={method} value={method}>
                {METHOD_LABELS[method]}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-ink-muted">
            <input
              type="checkbox"
              checked={Boolean(query.awaiting_verification)}
              onChange={(event) =>
                patch({ awaiting_verification: event.target.checked || undefined })
              }
              className="accent-gold"
            />
            Awaiting verification
          </label>
        </div>

        {error ? (
          <p role="alert" className="border-b border-line px-4 py-3 text-sm text-danger">
            {error}
          </p>
        ) : null}

        {loading ? (
          <p className="px-4 py-10 text-center text-sm text-stone">Loading payments…</p>
        ) : payments.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-stone">
            No payments match these filters.
          </p>
        ) : (
          <PaymentTable
            payments={payments}
            busyId={busyId}
            onVerify={(payment) =>
              act(payment.id, () => verifyBankTransfer(payment.id))
            }
            onReject={(payment, reason) =>
              act(payment.id, () => rejectBankTransfer(payment.id, reason))
            }
            onCollect={(payment) =>
              act(payment.id, () => markCodCollected(payment.id))
            }
          />
        )}

        <div className="flex items-center justify-between border-t border-line px-4 py-3 text-sm text-ink-muted">
          <span>
            {total} {total === 1 ? "payment" : "payments"}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={(query.page ?? 1) <= 1}
              onClick={() =>
                setQuery((c) => ({ ...c, page: Math.max(1, (c.page ?? 1) - 1) }))
              }
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              disabled={(query.page ?? 1) * (query.page_size ?? 25) >= total}
              onClick={() => setQuery((c) => ({ ...c, page: (c.page ?? 1) + 1 }))}
            >
              Next
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

function PaymentStatsRow({ stats }: { stats: PaymentStats | null }) {
  const tiles = useMemo(() => {
    if (!stats) return [];
    return [
      { label: "Collected", value: formatPrice(String(stats.collected_total)) },
      { label: "Pending", value: String(stats.status_counts.PENDING ?? 0) },
      { label: "Paid", value: String(stats.status_counts.PAID ?? 0) },
      { label: "Failed", value: String(stats.status_counts.FAILED ?? 0) },
      { label: "COD", value: String(stats.method_counts.COD ?? 0) },
      {
        label: "Bank transfer",
        value: String(stats.method_counts.BANK_TRANSFER ?? 0),
      },
      { label: "To verify", value: String(stats.awaiting_verification) },
    ];
  }, [stats]);

  if (!stats) return null;

  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden border border-line bg-line sm:grid-cols-4 lg:grid-cols-7">
      {tiles.map((tile) => (
        <div key={tile.label} className="bg-surface px-4 py-4">
          <p className="text-[11px] uppercase tracking-[0.12em] text-stone">
            {tile.label}
          </p>
          <p className="mt-1 font-serif text-xl text-ink">{tile.value}</p>
        </div>
      ))}
    </div>
  );
}

/**
 * States plainly which gateways are unavailable. Without this an operator could
 * reasonably assume PayFast works because it appears in the data model.
 */
function ProviderNotice({ providers }: { providers: PaymentProviderStatus[] }) {
  const pending = providers.filter((provider) => !provider.is_live);
  if (pending.length === 0) return null;

  return (
    <section className="border border-gold/40 bg-gold/5 p-4 sm:p-5">
      <h2 className="text-sm font-semibold text-ink">
        Gateways not yet available
      </h2>
      <p className="mt-1 text-sm text-ink-muted">
        These providers exist in the data model but have no working integration.
        Customers cannot select them at checkout.
      </p>
      <ul className="mt-3 space-y-2 text-sm">
        {pending.map((provider) => (
          <li key={provider.code} className="flex flex-wrap items-baseline gap-2">
            <span className="font-medium text-ink">{provider.display_name}</span>
            <span className="text-stone">— {provider.configuration_hint}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function PaymentTable({
  payments,
  busyId,
  onVerify,
  onReject,
  onCollect,
}: {
  payments: AdminPayment[];
  busyId: string | null;
  onVerify: (payment: AdminPayment) => void;
  onReject: (payment: AdminPayment, reason: string) => void;
  onCollect: (payment: AdminPayment) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[62rem] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-[11px] uppercase tracking-[0.12em] text-stone">
            <th className="px-4 py-3 font-medium">Order</th>
            <th className="px-4 py-3 font-medium">Customer</th>
            <th className="px-4 py-3 font-medium">Method</th>
            <th className="px-4 py-3 font-medium">Reference</th>
            <th className="px-4 py-3 text-right font-medium">Amount</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Created</th>
            <th className="px-4 py-3 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {payments.map((payment) => (
            <tr key={payment.id} className="border-b border-line/70 align-top">
              <td className="px-4 py-3">
                <Link
                  href={`/admin/orders/${payment.order_id}`}
                  className="font-mono text-ink underline decoration-gold/50 underline-offset-4"
                >
                  {payment.order_number}
                </Link>
              </td>
              <td className="px-4 py-3">
                <p className="text-ink">{payment.customer_name}</p>
                <p className="text-xs text-stone">{payment.customer_email}</p>
              </td>
              <td className="px-4 py-3 text-ink-muted">
                {METHOD_LABELS[payment.payment_method]}
              </td>
              <td className="px-4 py-3">
                {payment.customer_reference ? (
                  <span className="font-mono text-xs text-ink">
                    {payment.customer_reference}
                  </span>
                ) : payment.provider_transaction_id ? (
                  <span className="font-mono text-xs text-ink-muted">
                    {payment.provider_transaction_id}
                  </span>
                ) : (
                  <span className="text-stone">—</span>
                )}
                {payment.failure_reason ? (
                  <p className="mt-1 text-xs text-danger">
                    {payment.failure_reason}
                  </p>
                ) : null}
              </td>
              <td className="px-4 py-3 text-right font-medium text-ink">
                {formatPrice(payment.amount)}
              </td>
              <td className="px-4 py-3">
                <Badge tone={STATUS_TONES[payment.status]}>{payment.status}</Badge>
              </td>
              <td className="px-4 py-3 text-xs text-stone">
                {formatDateTime(payment.created_at)}
                {payment.paid_at ? (
                  <p className="text-success">
                    paid {formatDateTime(payment.paid_at)}
                  </p>
                ) : null}
              </td>
              <td className="px-4 py-3">
                <PaymentActions
                  payment={payment}
                  busy={busyId === payment.id}
                  onVerify={onVerify}
                  onReject={onReject}
                  onCollect={onCollect}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PaymentActions({
  payment,
  busy,
  onVerify,
  onReject,
  onCollect,
}: {
  payment: AdminPayment;
  busy: boolean;
  onVerify: (payment: AdminPayment) => void;
  onReject: (payment: AdminPayment, reason: string) => void;
  onCollect: (payment: AdminPayment) => void;
}) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  const settled =
    payment.status === "PAID" ||
    payment.status === "REFUNDED" ||
    payment.status === "CANCELLED";

  if (settled) {
    return <span className="text-xs text-stone">No action needed</span>;
  }

  if (payment.provider === "BANK_TRANSFER") {
    if (rejecting) {
      return (
        <div className="flex min-w-[14rem] flex-col gap-2">
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Why is it rejected?"
            className={`${SELECT} text-xs`}
            aria-label="Rejection reason"
          />
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={busy || reason.trim().length < 3}
              onClick={() => onReject(payment, reason.trim())}
            >
              Confirm
            </Button>
            <Button variant="ghost" onClick={() => setRejecting(false)}>
              Cancel
            </Button>
          </div>
        </div>
      );
    }
    return (
      <div className="flex flex-wrap gap-2">
        <Button disabled={busy} onClick={() => onVerify(payment)}>
          {busy ? "Saving…" : "Verify"}
        </Button>
        <Button variant="secondary" onClick={() => setRejecting(true)}>
          Reject
        </Button>
      </div>
    );
  }

  if (payment.provider === "COD") {
    return (
      <Button disabled={busy} onClick={() => onCollect(payment)}>
        {busy ? "Saving…" : "Cash received"}
      </Button>
    );
  }

  // Gateway payments settle through a verified webhook, never by hand.
  return (
    <span className="text-xs text-stone">
      Settled by gateway callback
    </span>
  );
}
