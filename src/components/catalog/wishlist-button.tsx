"use client";

import { Heart } from "lucide-react";
import { useState } from "react";

import { useStore } from "@/components/providers/store-provider";
import { cn } from "@/lib/utils";

/**
 * Save/unsave toggle.
 *
 * Anonymous selections are saved in local storage and merged after sign-in.
 */
export function WishlistButton({
  productId,
  productName,
  className,
  size = "md",
  withLabel = false,
}: {
  productId: string;
  productName: string;
  className?: string;
  size?: "sm" | "md";
  withLabel?: boolean;
}) {
  const { isWishlisted, toggleWishlist } = useStore();
  const [busy, setBusy] = useState(false);
  const saved = isWishlisted(productId);

  async function handleClick(event: React.MouseEvent) {
    // Cards wrap the whole tile in a link, so the click must not navigate.
    event.preventDefault();
    event.stopPropagation();

    setBusy(true);
    try {
      await toggleWishlist(productId);
    } catch {
      // Nothing destructive happened; the icon simply stays as it was.
    } finally {
      setBusy(false);
    }
  }

  const iconSize = size === "sm" ? "size-4" : "size-[18px]";

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      aria-pressed={saved}
      aria-label={saved ? `Remove ${productName} from wishlist` : `Save ${productName} to wishlist`}
      title={saved ? "Saved — click to remove" : "Save to wishlist"}
      className={cn(
        "inline-flex items-center justify-center gap-2 transition-colors disabled:opacity-50",
        className
      )}
    >
      <Heart
        className={cn(iconSize, saved ? "fill-gold text-gold" : "text-current")}
        aria-hidden
      />
      {withLabel ? (
        <span className="text-xs font-semibold uppercase tracking-[0.12em]">
          {saved ? "Saved" : "Save"}
        </span>
      ) : null}
    </button>
  );
}
