"use client";

import { Check, Loader2, ShoppingBag } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { WishlistButton } from "@/components/catalog/wishlist-button";
import { errorMessage, useStore } from "@/components/providers/store-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ProductVariant } from "@/lib/api/types";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Variant selection and add-to-bag.
 *
 * A sold-out variant is disabled on its own; the product stays selectable and
 * every other size remains choosable. Only when no variant has stock does the
 * add-to-bag control itself become unavailable.
 */
export function VariantPicker({
  variants,
  productPrice,
  productId,
  productName,
}: {
  variants: ProductVariant[];
  productPrice: string;
  productId: string;
  productName: string;
}) {
  const router = useRouter();
  const { isAuthenticated, addToCart } = useStore();

  const active = useMemo(() => variants.filter((variant) => variant.is_active), [variants]);
  const waistVariants = active.filter((variant) => variant.waist !== null);
  const sizeVariants = active.filter((variant) => variant.waist === null && variant.size !== null);
  const grouped = waistVariants.length > 0 ? waistVariants : sizeVariants;
  const groupLabel = waistVariants.length > 0 ? "Waist" : "Size";

  // Preselect the first purchasable variant so the page opens in a usable state.
  const [selectedId, setSelectedId] = useState<string | null>(
    () => grouped.find((variant) => variant.in_stock)?.id ?? null
  );
  const [quantity, setQuantity] = useState(1);
  const [status, setStatus] = useState<"idle" | "saving" | "added">("idle");
  const [error, setError] = useState<string | null>(null);

  const selected = grouped.find((variant) => variant.id === selectedId) ?? null;
  const anyInStock = active.some((variant) => variant.in_stock);
  // With no size axis at all, the single active variant is the purchasable unit.
  const fallbackVariant = grouped.length === 0 ? active.find((v) => v.in_stock) ?? null : null;
  const buyable = selected ?? fallbackVariant;
  const maxQuantity = Math.min(buyable?.quantity ?? 1, 10);
  const displayPrice = buyable?.price_override ?? productPrice;

  async function handleAdd() {
    if (!buyable) return;
    if (!isAuthenticated) {
      router.push(`/account?next=${encodeURIComponent(`/shop`)}`);
      return;
    }

    setStatus("saving");
    setError(null);
    try {
      await addToCart(buyable.id, quantity);
      setStatus("added");
      // Revert the confirmation so the button is reusable for another size.
      setTimeout(() => setStatus("idle"), 2500);
    } catch (caught) {
      setError(errorMessage(caught, "Could not add this to your bag."));
      setStatus("idle");
    }
  }

  return (
    <div className="border-t border-line pt-6">
      {grouped.length > 0 ? (
        <>
          <div className="flex items-center justify-between">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
              Select {groupLabel}
            </h2>
            {selected?.is_low_stock ? (
              <Badge tone="low">Only {selected.quantity} left</Badge>
            ) : null}
          </div>

          <div
            className="mt-3 flex flex-wrap gap-2"
            role="group"
            aria-label={`${groupLabel} options`}
          >
            {grouped.map((variant) => {
              const isSelected = variant.id === selectedId;
              const soldOut = !variant.in_stock;
              return (
                <button
                  key={variant.id}
                  type="button"
                  // Only this variant is disabled — never the whole product.
                  disabled={soldOut}
                  aria-pressed={isSelected}
                  aria-label={`${variant.label}${soldOut ? " — out of stock" : ""}`}
                  onClick={() => {
                    setSelectedId(variant.id);
                    setQuantity(1);
                    setError(null);
                  }}
                  className={cn(
                    "relative min-w-14 border px-4 py-2.5 text-sm transition-colors",
                    // Sold-out sizes stay legible: the shopper needs to read which
                    // size is gone, not just see that something is struck out.
                    soldOut && "cursor-not-allowed border-line bg-paper-alt text-stone",
                    !soldOut && isSelected && "border-ink bg-ink text-paper",
                    !soldOut &&
                      !isSelected &&
                      "border-line-strong text-ink hover:border-ink hover:bg-paper-alt"
                  )}
                >
                  {waistVariants.length > 0 ? variant.waist : variant.size}
                  {soldOut ? (
                    <span
                      aria-hidden
                      className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_top_right,transparent_48%,var(--color-line-strong)_48%,var(--color-line-strong)_52%,transparent_52%)]"
                    />
                  ) : null}
                </button>
              );
            })}
          </div>

          <div className="mt-3 min-h-5 text-xs">
            {selected ? (
              <p className="text-ink-muted">
                {selected.label} · {selected.quantity} in stock
                {selected.price_override ? ` · ${formatPrice(selected.price_override)}` : ""}
              </p>
            ) : anyInStock ? (
              <p className="text-gold-deep">
                Select an available {groupLabel.toLowerCase()} to continue
              </p>
            ) : (
              <p className="text-danger">Every size is currently sold out</p>
            )}
          </div>

          {grouped.some((variant) => !variant.in_stock) ? (
            <p className="mt-1 text-xs text-stone">
              Struck-through options are sold out in that {groupLabel.toLowerCase()} only.
            </p>
          ) : null}
        </>
      ) : (
        <p className="text-sm text-ink-muted">
          {anyInStock ? "One size — in stock." : "Currently unavailable."}
        </p>
      )}

      {buyable && maxQuantity > 1 ? (
        <div className="mt-5 flex items-center gap-3">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
            Quantity
          </span>
          <div className="flex items-center border border-line-strong">
            <button
              type="button"
              onClick={() => setQuantity((current) => Math.max(1, current - 1))}
              disabled={quantity <= 1}
              aria-label="Decrease quantity"
              className="grid size-9 place-items-center text-ink disabled:text-line-strong"
            >
              −
            </button>
            <span aria-live="polite" className="min-w-9 text-center text-sm">
              {quantity}
            </span>
            <button
              type="button"
              onClick={() => setQuantity((current) => Math.min(maxQuantity, current + 1))}
              disabled={quantity >= maxQuantity}
              aria-label="Increase quantity"
              className="grid size-9 place-items-center text-ink disabled:text-line-strong"
            >
              +
            </button>
          </div>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="mt-4 border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
          {error}
        </p>
      ) : null}

      <div className="mt-5 flex gap-2.5">
        <Button
          size="lg"
          className="flex-1"
          onClick={handleAdd}
          disabled={!buyable || status === "saving"}
        >
          {status === "saving" ? (
            <>
              <Loader2 className="size-4 animate-spin" aria-hidden />
              Adding…
            </>
          ) : status === "added" ? (
            <>
              <Check className="size-4" aria-hidden />
              Added to bag
            </>
          ) : (
            <>
              <ShoppingBag className="size-4" aria-hidden />
              {buyable ? "Add to bag" : "Unavailable"}
            </>
          )}
        </Button>
        <WishlistButton
          productId={productId}
          productName={productName}
          className="h-13 border border-line-strong px-4 text-ink hover:border-ink hover:bg-paper-alt"
        />
      </div>

      <div className="mt-3 min-h-5 text-xs">
        {status === "added" ? (
          <Link href="/cart" className="font-semibold text-gold-deep hover:text-ink">
            View bag and check out →
          </Link>
        ) : (
          <p className="text-stone">
            Price shown: {formatPrice(displayPrice)}. Cash on delivery and bank transfer available.
          </p>
        )}
      </div>
    </div>
  );
}
