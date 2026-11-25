/**
 * Homepage editorial sections: hero, the two scrolling bands, and the lookbook.
 *
 * Kept apart from `page.tsx` so the page stays a readable list of sections.
 */

import { MediaImage as Image } from "@/components/ui/media-image";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Marquee } from "@/components/home/marquee";
import { ButtonLink } from "@/components/ui/button";
import type { ProductListItem } from "@/lib/api/types";
import {
  EDITORIAL_PLATES,
  MIXED_PLATES,
  WOMENS_PLATES,
} from "@/lib/editorial";

/**
 * The two scrolling bands.
 *
 * Opposite directions on purpose: two rows travelling the same way reads as one
 * big moving block, whereas counter-motion gives the section a pulse without
 * anything blinking or bouncing. Both are slow — 70s and 86s per pass — because
 * fast marquees feel cheap.
 */
export function EditorialBands() {
  return (
    <section className="border-b border-line bg-paper-alt py-14 sm:py-20">
      <div className="mx-auto mb-9 max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-gold-deep">
              <span className="h-px w-8 bg-gold" aria-hidden />
              The rail
            </p>
            <h2 className="mt-3 font-display text-3xl text-ink sm:text-4xl">
              What just came in
            </h2>
          </div>
          <Link
            href="/shop"
            className="group inline-flex items-center gap-2 text-sm font-medium text-ink underline decoration-gold/40 underline-offset-[6px] transition-colors hover:decoration-gold"
          >
            Browse everything
            <ArrowRight
              className="size-4 transition-transform group-hover:translate-x-0.5"
              aria-hidden
            />
          </Link>
        </div>
      </div>

      <div className="space-y-3 sm:space-y-4">
        {/* Right-to-left */}
        <Marquee items={WOMENS_PLATES} direction="left" duration={70} priority />
        {/* Left-to-right */}
        <Marquee items={MIXED_PLATES} direction="right" duration={86} />
      </div>

      <p className="mx-auto mt-8 max-w-7xl px-4 text-[11px] text-stone sm:px-6 lg:px-8">
        Illustrated lookbook plates — photography of the actual pieces is on each product page.
      </p>
    </section>
  );
}

/**
 * Lookbook: an editorial grid where one plate spans two rows. The deliberate
 * asymmetry is what makes a grid feel art-directed rather than generated.
 */
export function Lookbook({ products = [] }: { products?: ProductListItem[] }) {
  const productPlates = [...new Map(products.map((product) => [product.id, product])).values()]
    .flatMap((product) => {
      const image = product.images.find((item) => item.is_primary) ?? product.images[0];
      return image
        ? [{ src: image.image_url, alt: image.alt_text ?? product.name, caption: product.category.name, href: `/shop/${product.slug}` }]
        : [];
    });
  const plates = productPlates.length ? productPlates.slice(0, 5) : EDITORIAL_PLATES.slice(0, 5);

  return (
    <section className="border-b border-line bg-surface py-16 sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-10 lg:grid-cols-12 lg:gap-14">
          <div className="lg:col-span-4 lg:self-center">
            <p className="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-gold-deep">
              <span className="h-px w-8 bg-gold" aria-hidden />
              Lookbook
            </p>
            <h2 className="mt-4 font-display text-4xl leading-[1.08] text-ink sm:text-5xl">
              Built around
              <br />
              <span className="italic text-gold-deep">what you already own.</span>
            </h2>
            <p className="mt-6 text-[15px] leading-[1.75] text-ink-muted">
              Hand-picked pieces, photographed as they are and ready to find a second life.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink href="/shop?gender=WOMEN">Shop women</ButtonLink>
              <ButtonLink href="/shop?gender=MEN" variant="secondary">
                Shop men
              </ButtonLink>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:col-span-8 lg:grid-cols-3">
            {plates.map((plate, index) => (
              <Link
                key={plate.src}
                href={plate.href ?? "/shop"}
                className={
                  // The first plate is tall; the rest fill around it.
                  index === 0
                    ? "group relative col-span-2 aspect-[4/5] overflow-hidden bg-paper-alt lg:col-span-2 lg:row-span-2 lg:aspect-auto"
                    : "group relative aspect-[4/5] overflow-hidden bg-paper-alt"
                }
              >
                <Image
                  src={plate.src}
                  alt={plate.alt}
                  fill
                  sizes={
                    index === 0
                      ? "(min-width: 1024px) 40vw, 100vw"
                      : "(min-width: 1024px) 20vw, 50vw"
                  }
                  className="object-cover transition-transform duration-[900ms] ease-out group-hover:scale-[1.03]"
                />
                <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-ink/85 via-ink/20 to-transparent px-4 pb-4 pt-12">
                  <span className="block text-[10px] font-semibold uppercase tracking-[0.18em] text-gold">
                    {plate.caption}
                  </span>
                  <span className="mt-0.5 flex items-center gap-1.5 text-sm text-paper">
                    Shop now
                    <ArrowRight
                      className="size-3.5 transition-transform group-hover:translate-x-1"
                      aria-hidden
                    />
                  </span>
                </span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
