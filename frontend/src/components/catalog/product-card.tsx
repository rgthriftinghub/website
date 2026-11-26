"use client";

import Link from "next/link";
import { Eye } from "lucide-react";

import { WishlistButton } from "@/components/catalog/wishlist-button";
import { useStore } from "@/components/providers/store-provider";
import { Badge } from "@/components/ui/badge";
import { MediaImage as Image } from "@/components/ui/media-image";
import { SaleBadge, SaleCountdown } from "@/components/catalog/sale-badge";
import type { ProductListItem } from "@/lib/api/types";
import { conditionLabel, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

function primaryImage(product: ProductListItem) {
  return product.images.find((image) => image.is_primary) ?? product.images[0] ?? null;
}

export function ProductCard({
  product,
  className,
  priority = false,
  sizes = "(min-width: 1280px) 22vw, (min-width: 768px) 30vw, 45vw",
}: {
  product: ProductListItem;
  className?: string;
  priority?: boolean;
  sizes?: string;
}) {
  const image = primaryImage(product);
  const soldOut = !product.in_stock;
  const { isWishlisted } = useStore();
  const saved = isWishlisted(product.id);

  return (
    <article className={cn("group relative flex flex-col", className)}>
      <Link href={`/shop/${product.slug}`} className="flex flex-col">
        {/* Fixed 3:4 ratio reserves the space before the image loads, so the
            grid never shifts. */}
        <div className="relative overflow-hidden bg-paper-alt aspect-[3/4]">
          {image ? (
            <Image
              src={image.image_url}
              alt={image.alt_text ?? product.name}
              fill
              sizes={sizes}
              priority={priority}
              className={cn("media-zoom object-cover", soldOut && "opacity-70")}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs uppercase tracking-widest text-stone">
              No image
            </div>
          )}

          <div className="absolute left-3 top-3 flex flex-col items-start gap-1.5">
            <Badge tone="neutral">{conditionLabel(product.condition)}</Badge>
            {/* Campaign badge takes precedence: it names the actual sale, which is
                more useful than a bare percentage. Falls back to the percentage for
                a plain manual markdown. */}
            {product.sale_pricing?.sale_id ? (
              <SaleBadge pricing={product.sale_pricing} />
            ) : product.is_on_sale ? (
              <Badge tone="sale">{product.discount_percent}% off</Badge>
            ) : null}
            {product.is_new_arrival ? <Badge tone="new">New in</Badge> : null}
          </div>

          {soldOut ? (
            <div className="absolute inset-x-0 bottom-0 bg-ink/85 py-2 text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-paper">
              Sold out
            </div>
          ) : null}
        </div>

        <div className="mt-3.5 flex flex-1 flex-col">
          <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-gold-deep">
            {product.brand?.name ?? product.category.name}
          </p>
          <h3 className="mt-1.5 font-display text-[15px] leading-snug text-ink">{product.name}</h3>
          {product.short_description ? (
            <p className="mt-1.5 line-clamp-2 text-xs leading-5 text-ink-muted">
              {product.short_description}
            </p>
          ) : null}
          {product.review_count > 0 ? (
            <p className="mt-1 text-xs text-ink-muted" aria-label={`${product.average_rating} out of 5 stars, ${product.review_count} reviews`}>
              <span className="text-gold-deep">★</span> {product.average_rating.toFixed(1)} ({product.review_count})
            </p>
          ) : null}

          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-sm font-semibold text-ink">
              {formatPrice(product.effective_price)}
            </span>
            {product.is_on_sale ? (
              <span className="text-xs text-stone line-through">
                {formatPrice(product.regular_price)}
              </span>
            ) : null}
          </div>

          {/* Only shown for a campaign with a real end time. */}
          <SaleCountdown pricing={product.sale_pricing} className="mt-1.5" />
        </div>
      </Link>

      {/* Quick actions. The wishlist toggle stays visible once saved, so the
          state is discoverable without hovering. */}
      <div
        className={cn(
          "absolute right-3 top-3 flex flex-col gap-2 transition-opacity duration-200",
          "opacity-0 group-hover:opacity-100 focus-within:opacity-100",
          saved && "opacity-100"
        )}
      >
        <WishlistButton
          productId={product.id}
          productName={product.name}
          size="sm"
          className="size-9 bg-paper/95 text-ink hover:bg-ink hover:text-paper"
        />
        <Link
          href={`/shop/${product.slug}`}
          title="View product"
          aria-label={`View ${product.name}`}
          className="grid size-9 place-items-center bg-paper/95 text-ink transition-colors hover:bg-ink hover:text-paper"
        >
          <Eye className="size-4" aria-hidden />
        </Link>
      </div>
    </article>
  );
}

export function ProductGrid({
  products,
  priorityCount = 0,
  className,
}: {
  products: ProductListItem[];
  priorityCount?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 gap-x-4 gap-y-9 sm:gap-x-5 lg:grid-cols-3 xl:grid-cols-4",
        className
      )}
    >
      {products.map((product, index) => (
        <ProductCard key={product.id} product={product} priority={index < priorityCount} />
      ))}
    </div>
  );
}
