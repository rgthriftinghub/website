"use client";

import Link from "next/link";
import { ArrowRight, ChevronLeft, ChevronRight, Package } from "lucide-react";
import { useEffect, useState } from "react";

import {
  OrderStatusPill,
  PAYMENT_METHOD_LABELS,
  PaymentStatusPill,
} from "@/components/orders/order-status";
import { ButtonLink } from "@/components/ui/button";
import { listMyOrders } from "@/lib/api/commerce";
import type { OrderSummary, Page } from "@/lib/api/types";
import { formatPrice } from "@/lib/format";

const PAGE_SIZE = 10;

export function OrderHistoryView() {
  const [data, setData] = useState<Page<OrderSummary> | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listMyOrders(page, PAGE_SIZE)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load your orders.");
      });
    return () => {
      cancelled = true;
    };
  }, [page]);

  if (error) {
    return <p className="mx-auto max-w-md px-4 py-24 text-center text-sm text-danger">{error}</p>;
  }

  if (data === null) {
    return (
      <div className="grid place-items-center py-28">
        <p className="text-sm text-stone" role="status">
          Loading your orders…
        </p>
      </div>
    );
  }

  if (data.total === 0) {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <span className="mx-auto grid size-16 place-items-center rounded-full bg-paper-alt">
          <Package className="size-6 text-gold-deep" aria-hidden />
        </span>
        <h1 className="mt-6 font-display text-3xl">No orders yet</h1>
        <p className="mt-3 text-sm text-ink-muted">
          When you place an order it will appear here with its full history.
        </p>
        <ButtonLink href="/shop" size="lg" className="mt-8">
          Start shopping
          <ArrowRight className="size-4" aria-hidden />
        </ButtonLink>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="border-b border-line pb-6">
        <Link
          href="/account"
          className="text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted hover:text-ink"
        >
          ← Account
        </Link>
        <p className="eyebrow mt-4">History</p>
        <h1 className="mt-2 text-4xl sm:text-5xl">Your orders</h1>
        <p className="mt-3 text-sm text-ink-muted">
          {data.total} order{data.total === 1 ? "" : "s"} placed.
        </p>
      </header>

      <ul className="mt-8 space-y-3">
        {data.items.map((order) => (
          <li key={order.id}>
            <Link
              href={`/account/orders/${order.order_number}`}
              className="group block border border-line bg-surface p-5 transition-colors hover:border-gold"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-mono text-sm font-semibold text-ink">{order.order_number}</p>
                  <p className="mt-1 text-xs text-stone">
                    {new Date(order.created_at).toLocaleDateString("en-PK", {
                      dateStyle: "medium",
                    })}{" "}
                    · {order.item_count} item{order.item_count === 1 ? "" : "s"} ·{" "}
                    {PAYMENT_METHOD_LABELS[order.payment_method]}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <OrderStatusPill status={order.order_status} />
                    <PaymentStatusPill status={order.payment_status} />
                  </div>
                </div>

                <div className="text-right">
                  <p className="font-display text-xl text-ink">
                    {formatPrice(order.total_amount)}
                  </p>
                  <span className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-gold-deep">
                    View order
                    <ArrowRight
                      className="size-3 transition-transform group-hover:translate-x-0.5"
                      aria-hidden
                    />
                  </span>
                </div>
              </div>
            </Link>
          </li>
        ))}
      </ul>

      {data.total_pages > 1 ? (
        <div className="mt-8 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            disabled={page <= 1}
            className="inline-flex h-10 items-center gap-1.5 border border-line-strong px-4 text-xs uppercase tracking-[0.12em] disabled:opacity-40"
          >
            <ChevronLeft className="size-3.5" aria-hidden />
            Previous
          </button>
          <p className="text-xs text-ink-muted">
            Page {data.page} of {data.total_pages}
          </p>
          <button
            type="button"
            onClick={() => setPage((current) => current + 1)}
            disabled={page >= data.total_pages}
            className="inline-flex h-10 items-center gap-1.5 border border-line-strong px-4 text-xs uppercase tracking-[0.12em] disabled:opacity-40"
          >
            Next
            <ChevronRight className="size-3.5" aria-hidden />
          </button>
        </div>
      ) : null}
    </div>
  );
}
