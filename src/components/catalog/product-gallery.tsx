"use client";

import Image from "next/image";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import type { ProductImage } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function ProductGallery({
  images,
  productName,
  discountPercent,
  isNewArrival,
}: {
  images: ProductImage[];
  productName: string;
  discountPercent: number;
  isNewArrival: boolean;
}) {
  const ordered = [...images].sort((a, b) => {
    if (a.is_primary !== b.is_primary) return a.is_primary ? -1 : 1;
    return a.sort_order - b.sort_order;
  });
  const [activeIndex, setActiveIndex] = useState(0);
  const active = ordered[activeIndex];

  return (
    <div className="flex flex-col gap-3 lg:flex-row-reverse lg:gap-4">
      {/* Main image keeps the 3:4 garment ratio at every breakpoint. */}
      <div className="relative flex-1 overflow-hidden bg-paper-alt aspect-[3/4]">
        {active ? (
          <Image
            src={active.image_url}
            alt={active.alt_text ?? productName}
            fill
            priority
            sizes="(min-width: 1024px) 45vw, 100vw"
            className="object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs uppercase tracking-widest text-stone">
            No image
          </div>
        )}

        <div className="absolute left-4 top-4 flex flex-col items-start gap-2">
          {discountPercent > 0 ? <Badge tone="sale">{discountPercent}% off</Badge> : null}
          {isNewArrival ? <Badge tone="new">New in</Badge> : null}
        </div>
      </div>

      {ordered.length > 1 ? (
        <ul
          className="no-scrollbar flex gap-3 overflow-x-auto lg:w-20 lg:flex-col lg:overflow-visible"
          aria-label={`${productName} images`}
        >
          {ordered.map((image, index) => (
            <li key={image.id} className="shrink-0">
              <button
                type="button"
                onClick={() => setActiveIndex(index)}
                aria-label={`Show image ${index + 1} of ${ordered.length}`}
                aria-current={index === activeIndex ? "true" : undefined}
                className={cn(
                  "relative block w-16 overflow-hidden border bg-paper-alt transition-colors aspect-[3/4] lg:w-full",
                  index === activeIndex
                    ? "border-ink"
                    : "border-transparent hover:border-line-strong"
                )}
              >
                <Image
                  src={image.image_url}
                  alt=""
                  fill
                  sizes="80px"
                  className="object-cover"
                />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
