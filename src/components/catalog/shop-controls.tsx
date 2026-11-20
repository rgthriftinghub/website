"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { SlidersHorizontal, X } from "lucide-react";
import { Suspense, useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import type { Brand, Category, FilterOptions, ProductSort } from "@/lib/api/types";
import { conditionLabel, formatPrice, productTypeLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

const SORT_OPTIONS: { value: ProductSort; label: string }[] = [
  { value: "newest", label: "Newest" },
  { value: "price_low", label: "Price: Low to High" },
  { value: "price_high", label: "Price: High to Low" },
  { value: "best_selling", label: "Best Selling" },
  { value: "highest_rated", label: "Highest Rated" },
];

const CONDITIONS = ["PREMIUM_PLUS", "PREMIUM", "EXCELLENT", "GOOD"] as const;
const GENDERS = ["MEN", "WOMEN", "UNISEX", "KIDS"] as const;
// ABAYA and KURTA are intentionally absent: the shop does not stock eastern wear.
// They remain valid backend enum values so any historical record stays readable.
const PRODUCT_TYPES = [
  "JEANS",
  "SHIRT",
  "T_SHIRT",
  "JACKET",
  "HOODIE",
  "SWEATER",
  "DRESS",
  "ACTIVEWEAR",
  "ACCESSORY",
] as const;

/** Query keys the filter UI owns; changing any of them resets pagination. */
const FILTER_KEYS = [
  "category",
  "subcategory",
  "brand",
  "gender",
  "condition",
  "product_type",
  "color",
  "fabric",
  "size",
  "waist",
  "availability",
  "min_price",
  "max_price",
  "is_featured",
  "is_new_arrival",
] as const;

function useFilterNavigation() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const setParam = useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(searchParams.toString());
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
      // Any filter change returns to page 1; staying on page 7 of a narrower
      // result set would show an empty grid.
      next.delete("page");
      router.push(`/shop?${next.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  const toggleParam = useCallback(
    (key: string, value: string) => {
      setParam(key, searchParams.get(key) === value ? null : value);
    },
    [searchParams, setParam]
  );

  const clearAll = useCallback(() => {
    const next = new URLSearchParams(searchParams.toString());
    for (const key of FILTER_KEYS) next.delete(key);
    next.delete("page");
    router.push(`/shop?${next.toString()}`, { scroll: false });
  }, [router, searchParams]);

  const activeCount = useMemo(
    () => FILTER_KEYS.filter((key) => searchParams.get(key)).length,
    [searchParams]
  );

  return { searchParams, setParam, toggleParam, clearAll, activeCount };
}

function FilterGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-line py-5">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">{title}</h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "border px-3 py-1.5 text-xs transition-colors",
        active
          ? "border-ink bg-ink text-paper"
          : "border-line-strong text-ink-muted hover:border-ink hover:text-ink"
      )}
    >
      {children}
    </button>
  );
}

function OptionList({
  items,
  paramKey,
  labelFor,
  searchParams,
  toggleParam,
}: {
  items: readonly (string | number)[];
  paramKey: string;
  labelFor?: (value: string) => string;
  searchParams: URLSearchParams;
  toggleParam: (key: string, value: string) => void;
}) {
  if (items.length === 0) {
    return <p className="text-xs text-stone">No options yet</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => {
        const value = String(item);
        return (
          <Chip
            key={value}
            active={searchParams.get(paramKey) === value}
            onClick={() => toggleParam(paramKey, value)}
          >
            {labelFor ? labelFor(value) : value}
          </Chip>
        );
      })}
    </div>
  );
}

interface FilterPanelProps {
  categories: Category[];
  brands: Brand[];
  options: FilterOptions;
}

/**
 * Every exported control here reads the query string via `useSearchParams`,
 * which opts the component out of static prerendering. Each is therefore
 * wrapped in its own Suspense boundary at the export site.
 */
export function FilterPanel(props: FilterPanelProps) {
  return (
    <Suspense fallback={<div className="h-96" />}>
      <FilterPanelInner {...props} />
    </Suspense>
  );
}

function FilterPanelInner({ categories, brands, options }: FilterPanelProps) {
  const { searchParams, setParam, toggleParam, clearAll, activeCount } = useFilterNavigation();
  const selectedCategory = categories.find((c) => c.slug === searchParams.get("category"));

  return (
    <div>
      <div className="flex items-center justify-between pb-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
          {activeCount > 0 ? `${activeCount} filter${activeCount > 1 ? "s" : ""} active` : "Filters"}
        </p>
        {activeCount > 0 ? (
          <button
            type="button"
            onClick={clearAll}
            className="text-[11px] font-semibold uppercase tracking-[0.1em] text-gold-deep hover:text-ink"
          >
            Clear all
          </button>
        ) : null}
      </div>

      <FilterGroup title="Category">
        <div className="flex flex-wrap gap-2">
          {categories.map((category) => (
            <Chip
              key={category.id}
              active={searchParams.get("category") === category.slug}
              onClick={() => {
                // Switching category invalidates any subcategory selection.
                if (searchParams.get("subcategory")) setParam("subcategory", null);
                toggleParam("category", category.slug);
              }}
            >
              {category.name}
            </Chip>
          ))}
        </div>
      </FilterGroup>

      {selectedCategory && selectedCategory.subcategories?.length ? (
        <FilterGroup title={`${selectedCategory.name} — Type`}>
          <OptionList
            items={selectedCategory.subcategories.map((s) => s.slug)}
            paramKey="subcategory"
            labelFor={(slug) =>
              selectedCategory.subcategories.find((s) => s.slug === slug)?.name ?? slug
            }
            searchParams={searchParams}
            toggleParam={toggleParam}
          />
        </FilterGroup>
      ) : null}

      <FilterGroup title="Brand">
        <OptionList
          items={brands.map((brand) => brand.slug)}
          paramKey="brand"
          labelFor={(slug) => brands.find((b) => b.slug === slug)?.name ?? slug}
          searchParams={searchParams}
          toggleParam={toggleParam}
        />
      </FilterGroup>

      <FilterGroup title="Size">
        <OptionList
          items={options.sizes}
          paramKey="size"
          searchParams={searchParams}
          toggleParam={toggleParam}
        />
      </FilterGroup>

      <FilterGroup title="Waist">
        <OptionList
          items={options.waists}
          paramKey="waist"
          searchParams={searchParams}
          toggleParam={toggleParam}
        />
      </FilterGroup>

      <FilterGroup title="Colour">
        <OptionList
          items={options.colors}
          paramKey="color"
          searchParams={searchParams}
          toggleParam={toggleParam}
        />
      </FilterGroup>

      <FilterGroup title="Fabric">
        <OptionList
          items={options.fabrics}
          paramKey="fabric"
          searchParams={searchParams}
          toggleParam={toggleParam}
        />
      </FilterGroup>

      <FilterGroup title="Gender">
        <OptionList
          items={GENDERS}
          paramKey="gender"
          labelFor={(value) => value.charAt(0) + value.slice(1).toLowerCase()}
          searchParams={searchParams}
          toggleParam={toggleParam}
        />
      </FilterGroup>

      <FilterGroup title="Condition">
        <OptionList
          items={CONDITIONS}
          paramKey="condition"
          labelFor={(value) => conditionLabel(value as (typeof CONDITIONS)[number])}
          searchParams={searchParams}
          toggleParam={toggleParam}
        />
      </FilterGroup>

      <FilterGroup title="Product Type">
        <OptionList
          items={PRODUCT_TYPES}
          paramKey="product_type"
          labelFor={productTypeLabel}
          searchParams={searchParams}
          toggleParam={toggleParam}
        />
      </FilterGroup>

      <FilterGroup title="Price">
        <PriceRange
          min={options.min_price}
          max={options.max_price}
          searchParams={searchParams}
          setParam={setParam}
        />
      </FilterGroup>

      <FilterGroup title="Availability">
        <div className="flex flex-wrap gap-2">
          <Chip
            active={searchParams.get("availability") === "in_stock"}
            onClick={() => toggleParam("availability", "in_stock")}
          >
            In stock
          </Chip>
          <Chip
            active={searchParams.get("availability") === "out_of_stock"}
            onClick={() => toggleParam("availability", "out_of_stock")}
          >
            Sold out
          </Chip>
        </div>
      </FilterGroup>

      <FilterGroup title="Collections">
        <div className="flex flex-wrap gap-2">
          <Chip
            active={searchParams.get("is_featured") === "true"}
            onClick={() => toggleParam("is_featured", "true")}
          >
            Featured
          </Chip>
          <Chip
            active={searchParams.get("is_new_arrival") === "true"}
            onClick={() => toggleParam("is_new_arrival", "true")}
          >
            New arrival
          </Chip>
        </div>
      </FilterGroup>
    </div>
  );
}

function PriceRange({
  min,
  max,
  searchParams,
  setParam,
}: {
  min: number | null;
  max: number | null;
  searchParams: URLSearchParams;
  setParam: (key: string, value: string | null) => void;
}) {
  const [from, setFrom] = useState(searchParams.get("min_price") ?? "");
  const [to, setTo] = useState(searchParams.get("max_price") ?? "");

  return (
    <div>
      {min !== null && max !== null ? (
        <p className="mb-2.5 text-xs text-stone">
          Catalogue range {formatPrice(min)} – {formatPrice(max)}
        </p>
      ) : null}
      <div className="flex items-center gap-2">
        <input
          type="number"
          min={0}
          inputMode="numeric"
          value={from}
          onChange={(event) => setFrom(event.target.value)}
          placeholder="Min"
          aria-label="Minimum price"
          className="h-10 w-full border border-line bg-paper px-2.5 text-sm outline-none focus:border-gold"
        />
        <span className="text-stone">–</span>
        <input
          type="number"
          min={0}
          inputMode="numeric"
          value={to}
          onChange={(event) => setTo(event.target.value)}
          placeholder="Max"
          aria-label="Maximum price"
          className="h-10 w-full border border-line bg-paper px-2.5 text-sm outline-none focus:border-gold"
        />
      </div>
      <Button
        variant="secondary"
        size="sm"
        className="mt-2.5 w-full"
        onClick={() => {
          setParam("min_price", from.trim() || null);
          setParam("max_price", to.trim() || null);
        }}
      >
        Apply price
      </Button>
    </div>
  );
}

export function SortSelect() {
  return (
    <Suspense fallback={<div className="h-10 w-32 border border-line" />}>
      <SortSelectInner />
    </Suspense>
  );
}

function SortSelectInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const current = searchParams.get("sort") ?? "newest";

  return (
    <label className="flex items-center gap-2 text-xs text-ink-muted">
      <span className="hidden sm:inline uppercase tracking-[0.12em]">Sort</span>
      <select
        value={current}
        onChange={(event) => {
          const next = new URLSearchParams(searchParams.toString());
          next.set("sort", event.target.value);
          next.delete("page");
          router.push(`/shop?${next.toString()}`, { scroll: false });
        }}
        className="h-10 border border-line bg-paper px-2.5 text-xs text-ink outline-none focus:border-gold"
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Mobile entry point: the same FilterPanel inside a slide-over drawer. */
export function FilterDrawer(props: FilterPanelProps) {
  return (
    <Suspense fallback={<div className="h-9 w-24 border border-line lg:hidden" />}>
      <FilterDrawerInner {...props} />
    </Suspense>
  );
}

function FilterDrawerInner(props: FilterPanelProps) {
  const [open, setOpen] = useState(false);
  const { activeCount } = useFilterNavigation();

  return (
    <>
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)} className="lg:hidden">
        <SlidersHorizontal className="size-3.5" aria-hidden />
        Filters
        {activeCount > 0 ? (
          <span className="grid size-4 place-items-center rounded-full bg-gold text-[9px] font-bold text-ink">
            {activeCount}
          </span>
        ) : null}
      </Button>

      {open ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close filters"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-ink/45"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Filters"
            className="absolute inset-y-0 right-0 flex w-[88%] max-w-sm flex-col bg-paper"
          >
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <h2 className="font-display text-lg">Filters</h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close filters"
                className="grid size-10 place-items-center text-ink"
              >
                <X className="size-5" aria-hidden />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 pb-4">
              <FilterPanel {...props} />
            </div>
            <div className="border-t border-line p-4">
              <Button className="w-full" onClick={() => setOpen(false)}>
                Show results
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
