import type { Metadata } from "next";
import Link from "next/link";
import { SearchX } from "lucide-react";

import { Pagination } from "@/components/catalog/pagination";
import { ProductGrid } from "@/components/catalog/product-card";
import { FilterDrawer, FilterPanel, SortSelect } from "@/components/catalog/shop-controls";
import { ButtonLink } from "@/components/ui/button";
import { getFilterOptions, listBrands, listCategories, listProducts } from "@/lib/api/catalog";
import type { Brand, Category, FilterOptions, Page, ProductListItem, ProductQuery } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "Shop All Products",
  description:
    "Browse the full RG Thrifting Hub catalogue. Filter by category, brand, size, waist, colour, fabric, condition and price.",
};

const PAGE_SIZE = 24;

/** Query keys forwarded from the URL to the API, so filters are honoured server-side. */
const PASSTHROUGH_KEYS = [
  "category",
  "subcategory",
  "brand",
  "gender",
  "condition",
  "product_type",
  "color",
  "fabric",
  "size",
  "availability",
  "search",
  "sort",
] as const;

type SearchParams = Record<string, string | string[] | undefined>;

function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function toProductQuery(searchParams: SearchParams): ProductQuery {
  const query: Record<string, unknown> = {};

  for (const key of PASSTHROUGH_KEYS) {
    const value = firstValue(searchParams[key]);
    if (value) query[key] = value;
  }

  for (const key of ["min_price", "max_price"] as const) {
    const value = firstValue(searchParams[key]);
    if (value && !Number.isNaN(Number(value))) query[key] = value;
  }

  const waist = firstValue(searchParams.waist);
  if (waist && Number.isInteger(Number(waist))) query.waist = Number(waist);

  for (const key of ["is_featured", "is_new_arrival"] as const) {
    if (firstValue(searchParams[key]) === "true") query[key] = true;
  }

  const page = Number(firstValue(searchParams.page) ?? "1");
  query.page = Number.isInteger(page) && page > 0 ? page : 1;
  query.page_size = PAGE_SIZE;

  return query as ProductQuery;
}

/** Rebuild the current URL with a different page, keeping every active filter. */
function pageHrefBuilder(searchParams: SearchParams) {
  return (page: number) => {
    const params = new URLSearchParams();
    for (const [key, raw] of Object.entries(searchParams)) {
      const value = firstValue(raw);
      if (value && key !== "page") params.set(key, value);
    }
    if (page > 1) params.set("page", String(page));
    const query = params.toString();
    return query ? `/shop?${query}` : "/shop";
  };
}

export default async function ShopPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const resolved = await searchParams;
  const query = toProductQuery(resolved);

  const [results, categories, brands, options] = await Promise.all([
    listProducts(query).catch(
      () =>
        ({ items: [], page: 1, page_size: PAGE_SIZE, total: 0, total_pages: 0 }) as Page<ProductListItem>
    ),
    listCategories().catch(() => [] as Category[]),
    listBrands().catch(() => [] as Brand[]),
    getFilterOptions().catch(
      () =>
        ({ colors: [], fabrics: [], sizes: [], waists: [], min_price: null, max_price: null }) as FilterOptions
    ),
  ]);

  const searchTerm = firstValue(resolved.search);
  const buildHref = pageHrefBuilder(resolved);
  const firstShown = results.total === 0 ? 0 : (results.page - 1) * results.page_size + 1;
  const lastShown = Math.min(results.page * results.page_size, results.total);

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="border-b border-line pb-7">
        <p className="eyebrow">The collection</p>
        <h1 className="mt-2 text-4xl sm:text-5xl">
          {searchTerm ? `Results for “${searchTerm}”` : "Shop all"}
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-ink-muted">
          Filter by size, waist, brand and condition. Availability reflects the stock we hold for
          each individual size.
        </p>
      </header>

      <div className="mt-8 lg:grid lg:grid-cols-[17rem_1fr] lg:gap-10">
        {/* Desktop sidebar. */}
        <aside className="hidden lg:block">
          <FilterPanel categories={categories} brands={brands} options={options} />
        </aside>

        <section>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
            <p className="text-xs text-ink-muted">
              {results.total === 0
                ? "No products"
                : `Showing ${firstShown}–${lastShown} of ${results.total} product${results.total === 1 ? "" : "s"}`}
            </p>
            <div className="flex items-center gap-2.5">
              {/* Mobile filter entry point. */}
              <FilterDrawer categories={categories} brands={brands} options={options} />
              <SortSelect />
            </div>
          </div>

          {results.items.length > 0 ? (
            <>
              <ProductGrid products={results.items} priorityCount={4} className="mt-8" />
              <Pagination
                page={results.page}
                totalPages={results.total_pages}
                buildHref={buildHref}
                className="mt-14"
              />
            </>
          ) : (
            <EmptyState searchTerm={searchTerm} />
          )}
        </section>
      </div>
    </div>
  );
}

function EmptyState({ searchTerm }: { searchTerm: string | undefined }) {
  return (
    <div className="flex flex-col items-center py-20 text-center">
      <SearchX className="size-8 text-line-strong" aria-hidden />
      <h2 className="mt-5 font-display text-2xl">Nothing matches those filters</h2>
      <p className="mt-2.5 max-w-sm text-sm text-ink-muted">
        {searchTerm
          ? `We could not find anything for “${searchTerm}”. Try a broader term or clear your filters.`
          : "Try removing a filter or two — the catalogue changes every week."}
      </p>
      <div className="mt-7 flex gap-2.5">
        <ButtonLink href="/shop" variant="secondary">
          Clear filters
        </ButtonLink>
        <ButtonLink href="/shop?is_new_arrival=true">See new arrivals</ButtonLink>
      </div>
      <Link
        href="/"
        className="mt-6 text-xs font-semibold uppercase tracking-[0.12em] text-gold-deep hover:text-ink"
      >
        Back to home
      </Link>
    </div>
  );
}
