"use client";

import { MediaImage as Image } from "@/components/ui/media-image";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Loader2, ShoppingBag, Trash2 } from "lucide-react";
import { useState } from "react";
import { useEffect } from "react";

import { errorMessage, useStore } from "@/components/providers/store-provider";
import { ButtonLink } from "@/components/ui/button";
import type { CartItem } from "@/lib/api/types";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { getCheckoutConfig } from "@/lib/api/commerce";
import type { CheckoutConfig } from "@/lib/api/types";

export function CartView() {
  const { cart, updateCartItem, removeCartItem } = useStore();
  const [busyItem, setBusyItem] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<CheckoutConfig | null>(null);
  useEffect(() => { void getCheckoutConfig().then(setConfig).catch(() => undefined); }, []);

  if (cart === null) {
    return (
      <div className="grid place-items-center py-28">
        <p className="text-sm text-stone" role="status">
          Loading your bag…
        </p>
      </div>
    );
  }

  if (cart.items.length === 0) {
    return <EmptyBag />;
  }

  async function change(itemId: string, quantity: number) {
    setBusyItem(itemId);
    setError(null);
    try {
      await updateCartItem(itemId, quantity);
    } catch (caught) {
      setError(errorMessage(caught, "Could not update that item."));
    } finally {
      setBusyItem(null);
    }
  }

  async function remove(itemId: string) {
    setBusyItem(itemId);
    setError(null);
    try {
      await removeCartItem(itemId);
    } catch (caught) {
      setError(errorMessage(caught, "Could not remove that item."));
    } finally {
      setBusyItem(null);
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="border-b border-line pb-6">
        <p className="eyebrow">Your bag</p>
        <h1 className="mt-2 text-4xl sm:text-5xl">Shopping bag</h1>
        <p className="mt-3 text-sm text-ink-muted">
          {cart.item_count} item{cart.item_count === 1 ? "" : "s"} ready to check out.
        </p>
      </header>

      {error ? (
        <p
          role="alert"
          className="mt-6 border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
        >
          {error}
        </p>
      ) : null}

      {cart.has_unavailable_items ? (
        <p className="mt-6 flex items-start gap-2.5 border border-gold/40 bg-gold-wash px-4 py-3 text-sm text-ink">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-gold-deep" aria-hidden />
          Some pieces are no longer available in the quantity you chose. Adjust or remove them to
          continue — one-of-a-kind stock moves quickly.
        </p>
      ) : null}

      <div className="mt-8 lg:grid lg:grid-cols-[1fr_22rem] lg:gap-10">
        <ul className="divide-y divide-line border-y border-line">
          {cart.items.map((item) => (
            <CartLine
              key={item.id}
              item={item}
              busy={busyItem === item.id}
              onChange={change}
              onRemove={remove}
            />
          ))}
        </ul>

        <aside className="mt-10 lg:mt-0">
          <div className="border border-line bg-surface p-6 lg:sticky lg:top-32">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Order summary
            </h2>
            {config?.free_delivery_threshold ? (() => { const threshold = Number(config.free_delivery_threshold); const subtotal = Number(cart.subtotal); const remaining = Math.max(0, threshold-subtotal); return <div className="mt-4" aria-live="polite"><p className="text-xs text-ink-muted">{remaining ? `Add ${formatPrice(String(remaining))} for free delivery` : "You have unlocked free delivery"}</p><div className="mt-2 h-2 overflow-hidden rounded-full bg-paper-alt"><div className="h-full bg-gold-deep transition-all" style={{width:`${Math.min(100,Math.max(0,subtotal/threshold*100))}%`}}/></div></div>; })() : null}

            <dl className="mt-5 space-y-2.5 text-sm">
              <Row label="Subtotal" value={formatPrice(cart.subtotal)} />
              <Row
                label="Delivery"
                value={
                  Number(cart.delivery_amount) === 0 ? "Free" : formatPrice(cart.delivery_amount)
                }
              />
              <div className="border-t border-line pt-3">
                <Row label="Total" value={formatPrice(cart.total)} emphasise />
              </div>
            </dl>

            <ButtonLink
              href="/checkout"
              size="lg"
              className={cn(
                "mt-6 w-full",
                cart.has_unavailable_items && "pointer-events-none opacity-45"
              )}
            >
              Proceed to checkout
              <ArrowRight className="size-4" aria-hidden />
            </ButtonLink>

            <ButtonLink href="/shop" variant="ghost" size="sm" className="mt-2.5 w-full">
              Continue shopping
            </ButtonLink>

            <p className="mt-5 border-t border-line pt-4 text-xs leading-relaxed text-stone">
              Cash on delivery and bank transfer are available at checkout. Delivery charges are
              calculated from your bag total.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  emphasise = false,
}: {
  label: string;
  value: string;
  emphasise?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className={emphasise ? "text-sm font-semibold text-ink" : "text-ink-muted"}>{label}</dt>
      <dd
        className={
          emphasise ? "font-display text-xl text-ink" : "tabular-nums text-ink"
        }
      >
        {value}
      </dd>
    </div>
  );
}

function CartLine({
  item,
  busy,
  onChange,
  onRemove,
}: {
  item: CartItem;
  busy: boolean;
  onChange: (itemId: string, quantity: number) => void;
  onRemove: (itemId: string) => void;
}) {
  const maxQuantity = Math.max(item.available_stock, 0);

  return (
    <li className={cn("flex gap-4 py-6 sm:gap-5", busy && "opacity-60")}>
      <Link
        href={`/shop/${item.product_slug}`}
        className="relative w-24 shrink-0 overflow-hidden bg-paper-alt aspect-[3/4] sm:w-28"
      >
        {item.image_url ? (
          <Image
            src={item.image_url}
            alt={item.product_name}
            fill
            sizes="112px"
            className="object-cover"
          />
        ) : null}
      </Link>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {item.brand_name ? (
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-gold-deep">
                {item.brand_name}
              </p>
            ) : null}
            <h3 className="mt-1 font-display text-base leading-snug">
              <Link href={`/shop/${item.product_slug}`} className="hover:text-gold-deep">
                {item.product_name}
              </Link>
            </h3>
            {/* The chosen variant is stated explicitly, not just implied. */}
            <p className="mt-1.5 text-xs text-ink-muted">
              {item.waist !== null ? `Waist ${item.waist}` : null}
              {item.waist !== null && item.size ? " · " : null}
              {item.size ? `Size ${item.size}` : null}
              {item.color ? ` · ${item.color}` : null}
            </p>
            <p className="mt-0.5 font-mono text-[11px] text-stone">{item.sku}</p>
          </div>

          <button
            type="button"
            onClick={() => onRemove(item.id)}
            disabled={busy}
            aria-label={`Remove ${item.product_name} from bag`}
            className="grid size-9 shrink-0 place-items-center text-stone transition-colors hover:text-danger"
          >
            {busy ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="size-4" aria-hidden />
            )}
          </button>
        </div>

        {!item.is_available ? (
          <p className="mt-2 inline-flex w-fit items-center gap-1.5 bg-danger/8 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-danger">
            <AlertTriangle className="size-3" aria-hidden />
            {item.unavailable_reason}
          </p>
        ) : null}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center border border-line-strong">
            <button
              type="button"
              onClick={() => onChange(item.id, item.quantity - 1)}
              disabled={busy || item.quantity <= 1}
              aria-label="Decrease quantity"
              className="grid size-9 place-items-center text-ink disabled:text-line-strong"
            >
              −
            </button>
            <span className="min-w-9 text-center text-sm tabular-nums">{item.quantity}</span>
            <button
              type="button"
              onClick={() => onChange(item.id, item.quantity + 1)}
              disabled={busy || item.quantity >= maxQuantity}
              aria-label="Increase quantity"
              className="grid size-9 place-items-center text-ink disabled:text-line-strong"
            >
              +
            </button>
          </div>

          <div className="text-right">
            <p className="text-sm font-semibold tabular-nums text-ink">
              {formatPrice(item.line_total)}
            </p>
            {item.quantity > 1 ? (
              <p className="text-xs text-stone">{formatPrice(item.unit_price)} each</p>
            ) : null}
          </div>
        </div>
      </div>
    </li>
  );
}

function EmptyBag() {
  return (
    <div className="mx-auto max-w-md px-4 py-24 text-center">
      <span className="mx-auto grid size-16 place-items-center rounded-full bg-paper-alt">
        <ShoppingBag className="size-6 text-gold-deep" aria-hidden />
      </span>
      <h1 className="mt-6 font-display text-3xl">Your bag is empty</h1>
      <p className="mt-3 text-sm text-ink-muted">
        Nothing saved yet. Every piece on the rail is one of a kind, so it is worth a look before
        it goes.
      </p>
      <div className="mt-8 flex justify-center gap-2.5">
        <ButtonLink href="/shop" size="lg">
          Continue shopping
          <ArrowRight className="size-4" aria-hidden />
        </ButtonLink>
      </div>
      <Link
        href="/wishlist"
        className="mt-6 inline-block text-xs font-semibold uppercase tracking-[0.12em] text-gold-deep hover:text-ink"
      >
        View your wishlist
      </Link>
    </div>
  );
}
