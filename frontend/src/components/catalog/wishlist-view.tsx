"use client";

import { ArrowRight, Heart } from "lucide-react";
import { useEffect, useState } from "react";

import { ProductCard } from "@/components/catalog/product-card";
import { useStore } from "@/components/providers/store-provider";
import { ButtonLink } from "@/components/ui/button";
import { getWishlist } from "@/lib/api/commerce";
import { getProductsByIds } from "@/lib/api/catalog";
import type { ProductListItem } from "@/lib/api/types";

export function WishlistView() {
  const { wishlistIds, isAuthenticated } = useStore();
  const [products, setProducts] = useState<ProductListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Refetching when the id set changes keeps the grid in step with hearts
  // toggled from this page or anywhere else in the session.
  useEffect(() => {
    let cancelled = false;
    (isAuthenticated
      ? getWishlist().then((result) => result.items.map((item) => item.product))
      : getProductsByIds([...wishlistIds])
    )
      .then((result) => { if (!cancelled) setProducts(result); })
      .catch(() => {
        if (!cancelled) setError("Could not load your wishlist.");
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, wishlistIds]);

  if (error) {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <p className="text-sm text-danger">{error}</p>
      </div>
    );
  }

  if (products === null) {
    return (
      <div className="grid place-items-center py-28">
        <p className="text-sm text-stone" role="status">
          Loading your wishlist…
        </p>
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <span className="mx-auto grid size-16 place-items-center rounded-full bg-paper-alt">
          <Heart className="size-6 text-gold-deep" aria-hidden />
        </span>
        <h1 className="mt-6 font-display text-3xl">Nothing saved yet</h1>
        <p className="mt-3 text-sm text-ink-muted">
          Tap the heart on any piece to keep it here while you decide.
        </p>
        <ButtonLink href="/shop" size="lg" className="mt-8">
          Browse the collection
          <ArrowRight className="size-4" aria-hidden />
        </ButtonLink>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="border-b border-line pb-6">
        <p className="eyebrow">Saved</p>
        <h1 className="mt-2 text-4xl sm:text-5xl">Your wishlist</h1>
        <p className="mt-3 text-sm text-ink-muted">
          {products.length} piece{products.length === 1 ? "" : "s"} saved. Stock is limited, so
          sizes can sell out while a piece sits here.
        </p>
      </header>

      <div className="mt-8 grid grid-cols-2 gap-x-4 gap-y-9 sm:gap-x-5 lg:grid-cols-3 xl:grid-cols-4">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
    </div>
  );
}
