import { MediaImage as Image } from "@/components/ui/media-image";
import Link from "next/link";

/** Editorial banner shared by the category and brand landing pages. */
export function CollectionHeader({
  eyebrow,
  title,
  description,
  imageUrl,
  imageAlt,
  links,
}: {
  eyebrow: string;
  title: string;
  description?: string | null;
  imageUrl?: string | null;
  imageAlt?: string;
  links?: { label: string; href: string }[];
}) {
  return (
    <section className="relative overflow-hidden bg-ink text-paper">
      {imageUrl ? (
        <Image
          src={imageUrl}
          alt=""
          fill
          priority
          sizes="100vw"
          className="object-cover opacity-45"
        />
      ) : null}

      <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
        <p className="eyebrow text-gold">{eyebrow}</p>
        <h1 className="mt-3 max-w-3xl text-4xl sm:text-5xl lg:text-6xl">{title}</h1>
        {description ? (
          <p className="mt-4 max-w-xl text-sm leading-relaxed text-paper/70">{description}</p>
        ) : null}

        {links && links.length > 0 ? (
          <nav aria-label={`${title} subcategories`} className="mt-8 flex flex-wrap gap-2">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="border border-paper/25 px-3.5 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-paper/85 transition-colors hover:border-gold hover:text-gold"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        ) : null}
      </div>

      {imageAlt ? <span className="sr-only">{imageAlt}</span> : null}
    </section>
  );
}
