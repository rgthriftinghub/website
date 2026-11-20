"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Heart, Menu, ShoppingBag, User, X } from "lucide-react";
import { useEffect, useState } from "react";

import { LogoLink } from "@/components/brand/logo";
import { SearchField } from "@/components/layout/search-field";
import { useStore } from "@/components/providers/store-provider";
import type { Category } from "@/lib/api/types";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  children?: NavItem[];
}

function buildNav(categories: Category[]): NavItem[] {
  return [
    { label: "Shop All", href: "/shop" },
    ...categories.map((category) => ({
      label: category.name,
      href: `/categories/${category.slug}`,
      children: category.subcategories
        .filter((subcategory) => subcategory.is_active)
        .map((subcategory) => ({
          label: subcategory.name,
          href: `/shop?category=${encodeURIComponent(category.slug)}&subcategory=${encodeURIComponent(subcategory.slug)}`,
        })),
    })),
    {
      label: "Shop by Condition",
      href: "/condition",
      children: [
        { label: "Premium Plus", href: "/condition/premium-plus" },
        { label: "Premium", href: "/condition/premium" },
        { label: "Excellent", href: "/condition/excellent" },
        { label: "Good", href: "/condition/good" },
        { label: "Condition Guide", href: "/condition-guide" },
      ],
    },
    { label: "New In", href: "/shop?is_new_arrival=true" },
    { label: "Sale", href: "/shop?sort=price_low" },
  ];
}

/** Small gold counter shown on the bag and wishlist icons. */
function CountBadge({ value }: { value: number }) {
  return (
    <span className="absolute right-0.5 top-1 grid min-w-4 place-items-center rounded-full bg-gold px-1 text-[9px] font-bold text-ink">
      {value > 99 ? "99+" : value}
    </span>
  );
}

export function Header({ categories }: { categories: Category[] }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { cartCount, wishlistCount } = useStore();
  const nav = buildNav(categories);

  // The drawer closes from its own link handlers, backdrop and Escape key, so
  // no effect needs to watch the pathname for it.

  // Prevent the page behind the drawer from scrolling.
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  // The bar is white rather than cream: the logo artwork is opaque
  // white-backed, so it only sits cleanly on a white surface.
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-surface">
      <p className="bg-ink px-4 py-2 text-center text-[11px] font-medium tracking-[0.1em] text-gold-soft">
        HAND-PICKED PIECES · NEW DROPS EVERY WEEK
      </p>

      <div className="mx-auto flex h-20 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:h-24 lg:px-8">
        {/* Mobile: hamburger, logo, cart. Desktop: full navigation. */}
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          aria-label="Open menu"
          aria-expanded={mobileOpen}
          className="-ml-2 grid size-10 place-items-center text-ink lg:hidden"
        >
          <Menu className="size-5" aria-hidden />
        </button>

        <LogoLink height={60} priority className="shrink-0 lg:hidden" />
        <LogoLink height={76} priority className="hidden shrink-0 lg:inline-flex" />

        <nav aria-label="Main" className="ml-6 hidden items-center gap-7 lg:flex">
          {nav.map((item) => (
            item.children ? (
              <div key={item.href} className="group relative">
                <Link href={item.href} aria-expanded="false" className="nav-link text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted hover:text-ink">{item.label}</Link>
                <div className="invisible absolute left-0 top-full z-50 min-w-52 translate-y-2 border border-line bg-surface p-2 opacity-0 shadow-lg transition-all group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100">
                  {item.children.map((child) => <Link key={child.href} href={child.href} className="block px-3 py-2.5 text-xs text-ink-muted hover:bg-paper-alt hover:text-ink">{child.label}</Link>)}
                </div>
              </div>
            ) : <Link key={item.href} href={item.href} data-active={pathname === item.href.split("?")[0] ? "true" : undefined} className="nav-link text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted hover:text-ink">{item.label}</Link>
          ))}
        </nav>

        <div className="ml-auto hidden max-w-xs flex-1 lg:block">
          <SearchField />
        </div>

        <div className="ml-auto flex items-center gap-1 lg:ml-3">
          <Link
            href="/account"
            aria-label="Account"
            className="grid size-10 place-items-center text-ink-muted transition-colors hover:text-ink"
          >
            <User className="size-[18px]" aria-hidden />
          </Link>
          <Link
            href="/wishlist"
            aria-label={`Wishlist${wishlistCount > 0 ? ` (${wishlistCount})` : ""}`}
            className="relative hidden size-10 place-items-center text-ink-muted transition-colors hover:text-ink sm:grid"
          >
            <Heart className="size-[18px]" aria-hidden />
            {wishlistCount > 0 ? <CountBadge value={wishlistCount} /> : null}
          </Link>
          <Link
            href="/cart"
            aria-label={`Bag${cartCount > 0 ? ` (${cartCount} items)` : " (empty)"}`}
            className="relative grid size-10 place-items-center text-ink-muted transition-colors hover:text-ink"
          >
            <ShoppingBag className="size-[18px]" aria-hidden />
            {cartCount > 0 ? <CountBadge value={cartCount} /> : null}
          </Link>
        </div>
      </div>

      {/* Search stays visible on mobile, where it is the primary way to browse. */}
      <div className="border-t border-line bg-paper px-4 py-2.5 lg:hidden">
        <SearchField />
      </div>

      {mobileOpen ? (
        <MobileDrawer nav={nav} onClose={() => setMobileOpen(false)} pathname={pathname} />
      ) : null}
    </header>
  );
}

function MobileDrawer({
  nav,
  pathname,
  onClose,
}: {
  nav: NavItem[];
  pathname: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <button
        type="button"
        aria-label="Close menu"
        onClick={onClose}
        className="absolute inset-0 bg-ink/45"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Menu"
        className="absolute inset-y-0 left-0 flex w-[84%] max-w-sm flex-col bg-surface"
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <LogoLink height={64} onClick={onClose} />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="grid size-10 place-items-center text-ink"
          >
            <X className="size-5" aria-hidden />
          </button>
        </div>

        <nav aria-label="Mobile" className="flex-1 overflow-y-auto px-5 py-4">
          {nav.map((item) => (
            <div key={item.href} className="border-b border-line">
              <Link href={item.href} onClick={onClose} className={cn("block py-3.5 font-display text-lg text-ink", pathname === item.href.split("?")[0] && "text-gold-deep")}>{item.label}</Link>
              {item.children?.map((child) => <Link key={child.href} href={child.href} onClick={onClose} className="block py-2 pl-4 text-sm text-ink-muted">{child.label}</Link>)}
            </div>
          ))}
        </nav>

        <div className="space-y-3 border-t border-line px-5 py-4">
          {[
            { href: "/account", label: "Account", icon: User },
            { href: "/wishlist", label: "Wishlist", icon: Heart },
            { href: "/cart", label: "Bag", icon: ShoppingBag },
          ].map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={onClose}
              className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink-muted hover:text-ink"
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
