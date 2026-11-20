import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CollectionHeader } from "@/components/catalog/collection-header";
import { ProductGrid } from "@/components/catalog/product-card";
import { Pagination } from "@/components/catalog/pagination";
import { ButtonLink } from "@/components/ui/button";
import { getCategory, listProducts } from "@/lib/api/catalog";
import type { Page, ProductListItem } from "@/lib/api/types";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<{ page?: string }> };
const PAGE_SIZE = 24;

async function load(slug: string) {
  try { return await getCategory(slug); } catch { notFound(); }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const category = await load(slug);
  return { title: `${category.name} | RG Thrifting Hub`, description: category.description || `Browse ${category.name} clothing at RG Thrifting Hub.` };
}

export default async function CategoryPage({ params, searchParams }: Props) {
  const [{ slug }, query] = await Promise.all([params, searchParams]);
  const category = await load(slug);
  const pageNum = Math.max(1, Number(query.page) || 1);
  const results = await listProducts({ category: category.slug, page: pageNum, page_size: PAGE_SIZE }).catch(
    () => ({ items: [], page: 1, page_size: PAGE_SIZE, total: 0, total_pages: 0 }) as Page<ProductListItem>
  );
  const base = `/categories/${category.slug}`;
  return <main>
    <CollectionHeader eyebrow="The collection" title={category.name} description={category.description} imageUrl={category.image_url} imageAlt={category.name} links={category.subcategories.map((sub) => ({ label: sub.name, href: `/shop?category=${encodeURIComponent(category.slug)}&subcategory=${encodeURIComponent(sub.slug)}` }))} />
    <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
        <p className="text-xs text-ink-muted">{results.total ? `Showing ${(results.page - 1) * PAGE_SIZE + 1}–${Math.min(results.page * PAGE_SIZE, results.total)} of ${results.total} pieces` : "No products in this collection yet"}</p>
        <ButtonLink href={`/shop?category=${encodeURIComponent(category.slug)}`} variant="secondary">Filter and sort {category.name}</ButtonLink>
      </div>
      {results.items.length ? <>
        <ProductGrid products={results.items} priorityCount={4} />
        <Pagination page={results.page} totalPages={results.total_pages} buildHref={(page) => page > 1 ? `${base}?page=${page}` : base} className="mt-12" />
      </> : <div className="py-16 text-center"><h2 className="font-display text-2xl">Nothing on this rail right now</h2><p className="mt-2 text-sm text-ink-muted">Try another collection or browse the full shop.</p><ButtonLink href="/shop" className="mt-6">Browse the shop</ButtonLink></div>}
    </section>
  </main>;
}
