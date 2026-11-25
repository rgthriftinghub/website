import { MediaImage as Image } from "@/components/ui/media-image";
import Link from "next/link";
import { ArrowRight, Recycle, ShieldCheck, Sparkles } from "lucide-react";

import { ProductCard } from "@/components/catalog/product-card";
import { ButtonLink } from "@/components/ui/button";
import { HeroCarousel } from "@/components/home/hero-carousel";
import { Lookbook } from "@/components/home/lookbook";
import { SectionHeading } from "@/components/ui/section-heading";
import { listBrands, listCategories, listProducts } from "@/lib/api/catalog";
import type { Brand, Category, ProductListItem } from "@/lib/api/types";
import { formatPrice } from "@/lib/format";

export const metadata = {
  title: "Curated Thrift & Export Quality Clothing",
  description:
    "Shop hand-picked thrift, export quality and new clothing at RG Thrifting Hub. Honest condition grading, per-size stock, and new drops every week.",
  openGraph: {
    title: "RG Thrifting Hub — Curated Thrift & Export Quality Clothing",
    description:
      "Hand-picked thrift, export quality and new clothing with honest condition grading.",
  },
};

interface HomeData {
  categories: Category[];
  brands: Brand[];
  newArrivals: ProductListItem[];
  featured: ProductListItem[];
  onSale: ProductListItem[];
}

async function loadHomeData(): Promise<HomeData> {
  // Fetched in parallel: none of these depend on each other.
  const [categories, brands, newArrivals, featured, sale] = await Promise.all([
    listCategories().catch(() => []),
    listBrands().catch(() => []),
    listProducts({ is_new_arrival: true, page_size: 8 }).catch(() => null),
    listProducts({ is_featured: true, page_size: 4 }).catch(() => null),
    listProducts({ sort: "price_low", page_size: 12 }).catch(() => null),
  ]);

  return {
    categories,
    brands,
    newArrivals: newArrivals?.items ?? [],
    featured: featured?.items ?? [],
    // The sale rail is derived from the discount flag the API already returns.
    onSale: (sale?.items ?? []).filter((product) => product.is_on_sale).slice(0, 4),
  };
}

export default async function HomePage() {
  const { categories, brands, newArrivals, featured, onSale } = await loadHomeData();

  return (
    <>
      <HeroCarousel
        images={newArrivals
          .map((product) => product.images.find((image) => image.is_primary) ?? product.images[0])
          .filter((image) => image !== undefined)
          .slice(0, 5)
          .map((image) => ({ src: image.image_url, alt: image.alt_text ?? "Preloved clothing" }))}
      />
      <Assurances />
      {categories.length > 0 ? <FeaturedCategories categories={categories} /> : null}
      <Lookbook products={[...featured, ...newArrivals]} />
      {newArrivals.length > 0 ? <NewArrivals products={newArrivals} /> : null}
      {featured.length > 0 ? <Featured products={featured} /> : null}
      {onSale.length > 0 ? <SaleRail products={onSale} /> : null}
      {brands.length > 0 ? <BrandStrip brands={brands} /> : null}
      <ClosingCta />
    </>
  );
}

const ASSURANCES = [
  {
    icon: ShieldCheck,
    title: "Honest grading",
    body: "New, Thrift or Export Quality — stated plainly on every product.",
  },
  {
    icon: Sparkles,
    title: "Checked by hand",
    body: "Inspected for wear, measured and photographed before listing.",
  },
  {
    icon: Recycle,
    title: "Stock per size",
    body: "Availability is tracked for each waist and size, not guessed.",
  },
];

function Assurances() {
  return (
    <section className="border-b border-line bg-paper-alt">
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-9 sm:grid-cols-3 sm:px-6 lg:px-8">
        {ASSURANCES.map(({ icon: Icon, title, body }) => (
          <div key={title} className="flex gap-3.5">
            <Icon className="mt-0.5 size-5 shrink-0 text-gold-deep" aria-hidden />
            <div>
              <p className="text-[13px] font-semibold text-ink">{title}</p>
              <p className="mt-0.5 text-[13px] leading-relaxed text-ink-muted">{body}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/**
 * Picture for a category card.
 *
 * Prefers the category's own uploaded image; otherwise falls back to an editorial
 * plate matched on the category name, so the row stays visually consistent with
 * the rest of the page rather than showing a placeholder of a different style.
 */
function categoryPlate(category: Category): string {
  if (category.image_url) return category.image_url;
  const name = category.name.toLowerCase();
  if (name.includes("women")) return "/editorial/women-coat-01.jpg";
  if (name.includes("men")) return "/editorial/men-jacket-01.jpg";
  if (name.includes("kid")) return "/editorial/women-sweater-01.jpg";
  return "/editorial/women-dress-01.jpg";
}

function FeaturedCategories({ categories }: { categories: Category[] }) {
  return (
    <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
      <SectionHeading
        eyebrow="Departments"
        title="Shop by category"
        description="Three departments, each curated separately and restocked every week."
        href="/shop"
      />

      <div className="mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {categories.map((category) => (
          <Link
            key={category.id}
            href={`/categories/${category.slug}`}
            className="group relative block overflow-hidden bg-ink aspect-[3/4] sm:aspect-[4/5]"
          >
            <Image
              src={categoryPlate(category)}
              alt={category.name}
              fill
              sizes="(min-width: 1024px) 32vw, (min-width: 640px) 48vw, 100vw"
              className="media-zoom object-cover opacity-95"
            />
            <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-ink/80 via-ink/10 to-transparent p-6">
              <h3 className="font-display text-2xl text-paper">{category.name}</h3>
              <p className="mt-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-gold">
                Shop now
                <ArrowRight className="size-3.5 transition-transform duration-200 group-hover:translate-x-1" aria-hidden />
              </p>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

function NewArrivals({ products }: { products: ProductListItem[] }) {
  return (
    <section className="border-t border-line bg-paper-alt/60">
      <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
        <SectionHeading
          eyebrow="Just landed"
          title="New arrivals"
          description="The most recent pieces to pass inspection."
          href="/shop?is_new_arrival=true"
        />
        <div className="mt-9 grid grid-cols-2 gap-x-4 gap-y-9 sm:gap-x-5 lg:grid-cols-4">
          {products.slice(0, 4).map((product, index) => (
            <ProductCard key={product.id} product={product} priority={index < 2} />
          ))}
        </div>
      </div>
    </section>
  );
}

function Featured({ products }: { products: ProductListItem[] }) {
  return (
    <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
      <SectionHeading
        eyebrow="Our picks"
        title="Featured this week"
        description="Pieces we would keep for ourselves."
        href="/shop?is_featured=true"
      />
      <div className="mt-9 grid grid-cols-2 gap-x-4 gap-y-9 sm:gap-x-5 lg:grid-cols-4">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
    </section>
  );
}

function SaleRail({ products }: { products: ProductListItem[] }) {
  const best = products.reduce(
    (highest, product) => Math.max(highest, product.discount_percent),
    0
  );

  return (
    <section className="border-y border-line bg-ink text-paper">
      <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-xl">
            <p className="eyebrow text-gold">Reduced</p>
            <h2 className="mt-2 text-3xl sm:text-4xl">
              Up to {best}% off selected pieces
            </h2>
            <p className="mt-3 text-sm text-paper/65">
              Marked down while stock lasts. Sizes are limited to what is on the rail.
            </p>
          </div>
          <Link
            href="/shop?sort=price_low"
            className="nav-link inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-gold"
          >
            Shop all reduced
            <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </div>

        <div className="mt-9 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {products.map((product) => {
            const image = product.images.find((i) => i.is_primary) ?? product.images[0];
            return (
              <Link
                key={product.id}
                href={`/shop/${product.slug}`}
                className="group block bg-ink-soft"
              >
                <div className="relative overflow-hidden aspect-[3/4]">
                  {image ? (
                    <Image
                      src={image.image_url}
                      alt={image.alt_text ?? product.name}
                      fill
                      sizes="(min-width: 1024px) 22vw, 45vw"
                      className="media-zoom object-cover"
                    />
                  ) : null}
                  <span className="absolute left-3 top-3 bg-gold px-2 py-1 text-[10px] font-bold uppercase tracking-[0.1em] text-ink">
                    −{product.discount_percent}%
                  </span>
                </div>
                <div className="p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-gold">
                    {product.brand?.name ?? "RG Select"}
                  </p>
                  <h3 className="mt-1.5 font-display text-[15px] leading-snug text-paper">
                    {product.name}
                  </h3>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-sm font-semibold text-paper">
                      {formatPrice(product.effective_price)}
                    </span>
                    <span className="text-xs text-paper/45 line-through">
                      {formatPrice(product.regular_price)}
                    </span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function BrandStrip({ brands }: { brands: Brand[] }) {
  return (
    <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
      <SectionHeading
        eyebrow="Labels"
        title="Discover the brands"
        description="The labels that come through our doors most often."
      />
      <div className="mt-9 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {brands.map((brand) => (
          <Link
            key={brand.id}
            href={`/brands/${brand.slug}`}
            className="group flex flex-col items-center gap-3 border border-line bg-paper p-5 text-center transition-colors hover:border-gold"
          >
            {brand.logo_url ? (
              <div className="relative size-20">
                <Image
                  src={brand.logo_url}
                  alt={brand.name}
                  fill
                  sizes="80px"
                  className="object-contain"
                />
              </div>
            ) : (
              <div className="grid size-20 place-items-center font-display text-2xl text-ink-muted">
                {brand.name.charAt(0)}
              </div>
            )}
            <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-muted group-hover:text-ink">
              {brand.name}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function ClosingCta() {
  return (
    <section className="mx-auto max-w-7xl px-4 pb-4 sm:px-6 lg:px-8">
      <div className="border border-line bg-gold-wash px-6 py-12 text-center sm:px-12 sm:py-16">
        <p className="eyebrow">Visit the rail</p>
        <h2 className="mx-auto mt-3 max-w-2xl text-3xl sm:text-4xl">
          Everything is one of a kind, so nothing waits long.
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-sm text-ink-muted">
          Browse the full catalogue and filter by size, waist, brand and condition to find pieces
          that actually fit.
        </p>
        <ButtonLink href="/shop" size="lg" className="mt-8">
          Browse all products
          <ArrowRight className="size-4" aria-hidden />
        </ButtonLink>
      </div>
    </section>
  );
}
