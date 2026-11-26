import type { Metadata } from "next";
import Link from "next/link";
import { ProductGallery } from "@/components/catalog/product-gallery";
import { ProductReviews } from "@/components/catalog/product-reviews";
import { VariantPicker } from "@/components/catalog/variant-picker";
import { ProductDescription } from "@/components/product-description";
import { getProduct } from "@/lib/api/catalog";
import { conditionLabel, formatPrice } from "@/lib/format";

type Props = { params: Promise<{ slug: string }> };
async function load(slug: string) {
  return getProduct(slug);
}
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const product = await load(slug);
  const description = product.meta_description || product.short_description || product.description || `${product.name} at RG Thrifting Hub.`;
  return { title: product.seo_title || product.name, description, openGraph: { title: product.seo_title || product.name, description, images: product.images[0] ? [product.images[0].image_url] : undefined } };
}
export default async function ProductPage({ params }: Props) {
  const { slug } = await params; const product = await load(slug);
  return <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
    <Link href="/shop" className="text-xs font-semibold uppercase tracking-wider text-ink-muted hover:text-ink">← Shop</Link>
    <div className="mt-6 grid gap-8 lg:grid-cols-2 lg:gap-12">
      <ProductGallery images={product.images} productName={product.name} discountPercent={product.discount_percent} isNewArrival={product.is_new_arrival} />
      <section className="lg:py-4"><p className="eyebrow">{product.brand?.name ?? product.category.name}</p><h1 className="mt-3 font-product-title text-3xl font-medium">{product.name}</h1>
        {product.short_description ? <ProductDescription text={product.short_description} className="mt-3 text-sm leading-6 text-ink-muted" /> : null}
        <p className="mt-3 text-sm text-ink-muted">{product.review_count ? `★ ${product.average_rating.toFixed(1)} · ${product.review_count} reviews` : "No ratings yet"}</p>
        <p className="mt-5 text-lg font-semibold">{formatPrice(product.effective_price)}</p>
        {product.description && product.description !== product.short_description ? <ProductDescription text={product.description} className="mt-5 text-sm leading-7 text-ink-muted" /> : null}
        <p className="mt-4 border-l-2 border-gold pl-3 text-xs leading-5 text-stone">
          {product.brand?.name
            ? `This pre-owned item is independently resold. RG Thrifting Hub is not affiliated with or endorsed by ${product.brand.name} or its brand owner.`
            : "RG Thrifting Hub is an independent reseller and is not affiliated with or endorsed by the original brand owners."}
        </p>
        <VariantPicker variants={product.variants} productPrice={product.effective_price} productId={product.id} productName={product.name} />
        <p className="mt-5"><span className="inline-flex border border-line-strong px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]">{conditionLabel(product.condition)}</span></p>
        <p className="mt-3 text-xs text-stone">{product.color ?? ""} {product.fabric ?? ""}</p>
      </section>
    </div>
    <ProductReviews slug={slug} average={product.average_rating} count={product.review_count} />
  </main>;
}
