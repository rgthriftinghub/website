import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";

import { Pagination } from "@/components/catalog/pagination";
import { ProductGrid } from "@/components/catalog/product-card";
import { SortSelect } from "@/components/catalog/shop-controls";
import { ButtonLink } from "@/components/ui/button";
import { listProducts } from "@/lib/api/catalog";
import type { Page, ProductCondition, ProductListItem, ProductSort } from "@/lib/api/types";
import { conditionLabel } from "@/lib/format";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<{ page?: string; sort?: string }> };
const PAGE_SIZE = 24;
const GRADES: Record<string, ProductCondition> = {
  "premium-plus": "PREMIUM_PLUS", premium: "PREMIUM", excellent: "EXCELLENT", good: "GOOD",
};

async function gradeFor(slug: string) {
  const grade = GRADES[slug];
  if (!grade) notFound();
  return grade;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const grade = await gradeFor(slug);
  return { title: `${conditionLabel(grade)} Clothing | RG Thrifting Hub`, description: `Shop pre-loved clothing graded ${conditionLabel(grade)}. Every piece is checked by hand at RG Thrifting Hub.` };
}

export default async function ConditionCollectionPage({ params, searchParams }: Props) {
  const [{ slug }, query] = await Promise.all([params, searchParams]);
  const grade = await gradeFor(slug);
  const pageNum = Math.max(1, Number(query.page) || 1);
  const allowedSorts: ProductSort[] = ["newest", "price_low", "price_high", "best_selling", "highest_rated"];
  const sort = allowedSorts.includes(query.sort as ProductSort) ? query.sort as ProductSort : "newest";
  const results = await listProducts({ condition: grade, sort, page: pageNum, page_size: PAGE_SIZE }).catch(
    () => ({ items: [], page: 1, page_size: PAGE_SIZE, total: 0, total_pages: 0 }) as Page<ProductListItem>
  );
  const base = `/condition/${slug}`;
  return <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
    <nav aria-label="Breadcrumb" className="text-xs text-ink-muted"><Link href="/condition" className="underline underline-offset-4">Shop by Condition</Link><span className="mx-2">/</span><span>{conditionLabel(grade)}</span></nav>
    <header className="mt-5 border-b border-line pb-7"><p className="eyebrow">Condition collection</p><h1 className="mt-2 font-display text-4xl">{conditionLabel(grade)}</h1><p className="mt-3 max-w-2xl text-sm text-ink-muted">Hand-checked pre-loved pieces with condition described clearly on every product.</p></header>
    <section className="mt-7">
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4"><p className="text-xs text-ink-muted">{results.total ? `${results.total} pieces in this grade` : "No products in this grade yet"}</p><div className="flex items-center gap-3"><SortSelect /><ButtonLink href={`/shop?condition=${grade}`} variant="secondary" size="sm">All filters</ButtonLink></div></div>
      {results.items.length ? <><ProductGrid products={results.items} priorityCount={4} /><Pagination page={results.page} totalPages={results.total_pages} buildHref={(page) => { const params = new URLSearchParams({ sort }); if (page > 1) params.set("page", String(page)); return `${base}?${params}`; }} className="mt-12" /></> : <div className="py-16 text-center"><h2 className="font-display text-2xl">No pieces in this grade yet</h2><p className="mt-2 text-sm text-ink-muted">Browse another condition grade or explore the full shop.</p><ButtonLink href="/condition" className="mt-6">Choose another grade</ButtonLink></div>}
    </section>
  </main>;
}
