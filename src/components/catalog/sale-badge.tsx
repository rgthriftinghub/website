"use client";

/**
 * Storefront sale badge and flash countdown.
 *
 * The badge text, discount, and end time all come from the backend's resolved
 * `sale_pricing`. **The countdown is presentation only** — it never decides whether
 * a sale applies. When it reaches zero the price does not change client-side; the
 * next request simply returns the undiscounted price, because the server owns the
 * activation rule.
 */

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";
import type { SalePricing, SaleType } from "@/lib/api/types";

const TONES: Record<SaleType, string> = {
  FLASH: "bg-danger text-paper",
  CLEARANCE: "bg-ink text-gold",
  SEASONAL: "bg-gold text-ink",
  STANDARD: "bg-gold text-ink",
};

export function SaleBadge({
  pricing,
  className,
}: {
  pricing: SalePricing | null | undefined;
  className?: string;
}) {
  if (!pricing?.sale_id || pricing.discount_percent <= 0) return null;
  const tone = TONES[pricing.sale_type ?? "STANDARD"];

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
        tone,
        className
      )}
    >
      {pricing.badge_text ?? "Sale"} · {pricing.discount_percent}% off
    </span>
  );
}

function remaining(endsAt: string): { text: string; expired: boolean } {
  const milliseconds = new Date(endsAt).getTime() - Date.now();
  if (Number.isNaN(milliseconds) || milliseconds <= 0) {
    return { text: "Ending now", expired: true };
  }
  const totalSeconds = Math.floor(milliseconds / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (days > 0) return { text: `${days}d ${hours}h left`, expired: false };
  const pad = (value: number) => String(value).padStart(2, "0");
  return { text: `${pad(hours)}:${pad(minutes)}:${pad(seconds)} left`, expired: false };
}

/**
 * Live countdown for a time-limited campaign.
 *
 * Only rendered for a sale that actually has an end time, so an open-ended
 * clearance rail does not display a meaningless timer.
 */
export function SaleCountdown({
  pricing,
  className,
}: {
  pricing: SalePricing | null | undefined;
  className?: string;
}) {
  const endsAt = pricing?.ends_at ?? null;
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    if (!endsAt) return;

    const tick = () => {
      const next = remaining(endsAt);
      setLabel(next.text);
      if (next.expired) window.clearInterval(timer);
    };

    // The first tick is deferred to a macrotask rather than run inline. Two
    // reasons: the effect body then performs no synchronous state update, and a
    // clock rendered into the initial HTML would hydrate mismatched against the
    // client's own clock. The delay is imperceptible.
    const immediate = window.setTimeout(tick, 0);
    const timer = window.setInterval(tick, 1000);

    return () => {
      window.clearTimeout(immediate);
      window.clearInterval(timer);
    };
  }, [endsAt]);

  if (!pricing?.sale_id || !endsAt || !label) return null;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-[11px] font-medium tabular-nums text-danger",
        className
      )}
      aria-live="off"
    >
      <span className="inline-block size-1.5 animate-pulse rounded-full bg-danger" aria-hidden />
      {label}
    </span>
  );
}

/** Price block: original struck through, campaign price, and the saving. */
export function SalePrice({
  pricing,
  regularPrice,
  effectivePrice,
  formatPrice,
  size = "default",
}: {
  pricing: SalePricing | null | undefined;
  regularPrice: string;
  effectivePrice: string;
  formatPrice: (value: string | number) => string;
  size?: "default" | "large";
}) {
  const discounted = Number(effectivePrice) < Number(regularPrice);
  const saving = pricing?.discount_amount;

  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span
        className={cn(
          "font-medium text-ink",
          size === "large" ? "text-2xl" : "text-sm",
          discounted ? "text-danger" : ""
        )}
      >
        {formatPrice(effectivePrice)}
      </span>
      {discounted ? (
        <>
          <span
            className={cn(
              "text-stone line-through",
              size === "large" ? "text-base" : "text-xs"
            )}
          >
            {formatPrice(regularPrice)}
          </span>
          {saving && Number(saving) > 0 ? (
            <span
              className={cn(
                "text-gold-deep",
                size === "large" ? "text-sm" : "text-[11px]"
              )}
            >
              Save {formatPrice(saving)}
            </span>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
