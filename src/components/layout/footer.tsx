import Link from "next/link";
// lucide-react v1 no longer ships brand marks, so the social handle uses AtSign.
import { AtSign, Mail, MapPin, Phone } from "lucide-react";

import { Logo } from "@/components/brand/logo";
import type { Category } from "@/lib/api/types";
import { THRIFT_DISCLAIMER } from "@/lib/disclaimer";

const HELP_LINKS = [
  // Only the tracker is a real destination so far; the rest point at the shop
  // until those pages exist, rather than 404ing.
  { label: "Track Your Order", href: "/track-order" },
  { label: "Size & Fit Guide", href: "/shop" },
  { label: "Shop by Condition", href: "/condition" },
  { label: "Condition Guide", href: "/condition-guide" },
  { label: "Shipping", href: "/pages/shipping" },
  { label: "Return & Exchange", href: "/pages/returns" },
  { label: "Refund", href: "/pages/refund" },
  { label: "Privacy", href: "/pages/privacy" },
  { label: "FAQ", href: "/pages/faq" },
  { label: "About", href: "/pages/about" },
  { label: "Contact Us", href: "/pages/contact" },
];

export function Footer({ categories }: { categories: Category[] }) {
  return (
    <footer className="mt-24 border-t border-line bg-ink text-paper">
      <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            {/* On the dark footer the opaque logo sits on a deliberate white
                plate rather than showing an accidental white halo. */}
            <div className="inline-block rounded-sm bg-surface p-3">
              <Logo height={84} />
            </div>
            <p className="mt-5 max-w-xs text-sm leading-relaxed text-paper/65">
              Curated thrift, export quality and new clothing. Every piece is checked by hand and
              graded honestly before it reaches the shop.
            </p>
            <span className="rule-gold mt-6" />
          </div>

          <nav aria-label="Shop">
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gold">
              Shop
            </h3>
            <ul className="mt-4 space-y-2.5 text-sm text-paper/65">
              <li>
                <Link href="/shop" className="transition-colors hover:text-paper">
                  All Products
                </Link>
              </li>
              {categories.map((category) => (
                <li key={category.id}>
                  <Link
                    href={`/categories/${category.slug}`}
                    className="transition-colors hover:text-paper"
                  >
                    {category.name}
                  </Link>
                </li>
              ))}
              <li>
                <Link
                  href="/shop?is_new_arrival=true"
                  className="transition-colors hover:text-paper"
                >
                  New Arrivals
                </Link>
              </li>
            </ul>
          </nav>

          <nav aria-label="Help">
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gold">
              Help
            </h3>
            <ul className="mt-4 space-y-2.5 text-sm text-paper/65">
              {HELP_LINKS.map((link) => (
                <li key={link.label}>
                  <Link href={link.href} className="transition-colors hover:text-paper">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div>
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gold">
              Visit & Contact
            </h3>
            <ul className="mt-4 space-y-3 text-sm text-paper/65">
              <li className="flex gap-2.5">
                <MapPin className="mt-0.5 size-4 shrink-0 text-gold" aria-hidden />
                Lahore, Pakistan
              </li>
              <li className="flex gap-2.5">
                <Phone className="mt-0.5 size-4 shrink-0 text-gold" aria-hidden />
                0300 164 5089
              </li>
              <li className="flex gap-2.5">
                <Mail className="mt-0.5 size-4 shrink-0 text-gold" aria-hidden />
                hello@rgthriftinghub.pk
              </li>
              <li className="flex gap-2.5">
                <AtSign className="mt-0.5 size-4 shrink-0 text-gold" aria-hidden />
                <a href="https://www.instagram.com/rg_thriftinghub?gwpx=aHZtcmtlbXB5dXZj" target="_blank" rel="noreferrer">
                  @rgthriftinghub
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 border-t border-paper/12 pt-6">
          <p className="max-w-4xl text-xs leading-relaxed text-paper/65">{THRIFT_DISCLAIMER}</p>
          <div className="mt-4 flex flex-col gap-3 text-xs text-paper/45 sm:flex-row sm:items-center sm:justify-between">
            <p>© {new Date().getFullYear()} RG Thrifting Hub. All rights reserved.</p>
            <p>Online ordering and payments are coming soon.</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
